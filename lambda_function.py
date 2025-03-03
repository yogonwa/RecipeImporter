import json
import logging
import os
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse
from recipe_scrapers import scrape_me
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode
from notion_client import Client
from notion_client.errors import APIResponseError
from datetime import datetime
import requests

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Notion configuration
NOTION_API_KEY = os.environ.get('NOTION_API_KEY')
NOTION_DATABASE_ID = os.environ.get('NOTION_DATABASE_ID')

# Initialize Notion client
try:
    notion = Client(auth=NOTION_API_KEY) if NOTION_API_KEY else None
    if notion:
        logger.info(f"Notion client initialized with API key: {NOTION_API_KEY[:10]}...")
    else:
        logger.error("No Notion API key provided")
except Exception as e:
    logger.error(f"Error initializing Notion client: {str(e)}")
    notion = None

def is_valid_url(url: str) -> bool:
    """
    Check if the provided URL is valid and uses HTTP/HTTPS.
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except Exception:
        return False

def get_page_id_from_unique_id(unique_id: str) -> Optional[str]:
    """
    Look up a page ID from a unique ID by querying the Notion database.
    Returns the page ID if found, None otherwise.
    """
    if not notion or not NOTION_DATABASE_ID:
        logger.error("Notion client or database ID not configured")
        return None

    try:
        # Parse the unique ID number from the format (e.g., "CB-11" -> 11)
        try:
            unique_id_number = int(unique_id.split('-')[1])
        except (IndexError, ValueError):
            logger.error(f"Invalid unique ID format: {unique_id}")
            return None

        # Query the database for the page with matching unique ID number
        response = notion.databases.query(
            database_id=NOTION_DATABASE_ID,
            filter={
                "property": "Unique ID",
                "unique_id": {
                    "equals": unique_id_number
                }
            }
        )

        # Check if we found a matching page
        if response["results"]:
            return response["results"][0]["id"]
        else:
            logger.error(f"No page found with unique ID number: {unique_id_number}")
            return None

    except Exception as e:
        logger.error(f"Error looking up page ID from unique ID: {str(e)}")
        return None

def extract_notion_page_info(event: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """
    Extract page info from Notion webhook event.
    Now supports both direct page ID and unique ID.
    Returns tuple of (page_id, url) if valid, None if invalid.
    """
    try:
        # Check if 'body' exists (for API Gateway-wrapped requests)
        if "body" in event:
            body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        else:
            body = event  # Direct payload (Notion webhook)

        # Determine where to extract data from
        if "data" in body:  # Notion webhook format
            page_data = body["data"]
            properties = page_data.get("properties", {})
            page_id = page_data.get("id")

        elif "page" in body:  # API Gateway test format
            page_data = body["page"]
            properties = page_data.get("properties", {})
            page_id = page_data.get("id")

        else:
            logger.error("Invalid webhook format: No 'data' or 'page' field found")
            return None

        # Extract URL from properties
        url = None
        if "Link" in properties:
            if properties["Link"].get("type") == "url":  # Notion webhook format
                url = properties["Link"]["url"]
            elif "rich_text" in properties["Link"]:  # API Gateway test format
                url = properties["Link"]["rich_text"][0]["text"]["content"]

        if not url or not is_valid_url(url):
            logger.error(f"Invalid or missing URL in properties: {url}")
            return None

        # Extract unique ID
        unique_id_prop = properties.get("Unique ID", {}).get("unique_id", {})
        if unique_id_prop:
            unique_id = f"{unique_id_prop.get('prefix', 'CB')}-{unique_id_prop.get('number')}"
            page_id = get_page_id_from_unique_id(unique_id) or page_id

        if not page_id:
            logger.error("Failed to get page ID from event")
            return None

        logger.info(f"Successfully extracted page info - ID: {page_id}, URL: {url}")
        return (page_id, url)

    except Exception as e:
        logger.error(f"Error extracting page info: {str(e)}")
        return None

def create_import_details_block(parsing_methods: Dict[str, str], timestamp: str) -> Dict[str, Any]:
    """
    Create a collapsible import details block showing how each field was parsed.
    
    Args:
        parsing_methods: Dict mapping field names to their parsing method
        timestamp: ISO format timestamp of when parsing occurred
    """
    details_text = "Import Details:\n"
    for field, method in parsing_methods.items():
        details_text += f"- {field}: {method}\n"
    details_text += f"Timestamp: {timestamp}"
    
    return {
        "type": "toggle",
        "toggle": {
            "rich_text": [{
                "type": "text",
                "text": {"content": "🔍 Import Details"}
            }],
            "children": [{
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": details_text}
                    }]
                }
            }]
        }
    }

def extract_recipe_with_gpt(html_content: str) -> Dict[str, Any]:
    """
    Use GPT to extract recipe information from raw HTML when other methods fail.
    Returns a dictionary with recipe data or None if extraction fails.
    """
    try:
        # Note: Implementation will require adding OpenAI API integration
        # This is a placeholder structure for the GPT-based extraction
        
        prompt = f"""Extract recipe information from the following HTML content.
        Focus on finding:
        1. Title
        2. Ingredients (as a list)
        3. Instructions (as steps)
        4. Cooking time and servings if available
        
        HTML Content:
        {html_content[:8000]}  # Truncate to fit token limits
        """
        
        # TODO: Add OpenAI API call here
        # response = openai.ChatCompletion.create(...)
        
        return {
            "title": "TODO",
            "ingredients": [],
            "instructions": [],
            "parsing_methods": {"all_fields": "gpt-fallback"},
            "parse_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"GPT extraction failed: {str(e)}")
        return None

def scrape_recipe(url: str) -> Dict[str, Any]:
    """
    Scrape recipe data with multiple fallback methods.
    """
    try:
        # Try standard scraping first
        recipe_data = try_standard_scraping(url)
        if recipe_data and not recipe_data.get("error"):
            return recipe_data
            
        # If standard scraping fails, try wild mode
        recipe_data = try_wild_mode_scraping(url)
        if recipe_data and not recipe_data.get("error"):
            return recipe_data
            
        # If both fail, try GPT-based extraction
        html_content = requests.get(url).text
        recipe_data = extract_recipe_with_gpt(html_content)
        if recipe_data:
            recipe_data["url"] = url
            return recipe_data
            
        return {"error": "All extraction methods failed"}
        
    except Exception as e:
        logger.error(f"Recipe extraction failed: {str(e)}")
        return {"error": str(e)}

def create_notion_blocks(recipe_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Create Notion blocks from recipe data.
    Creates a two-column layout with ingredients on the left and yield/nutrition on the right.
    Instructions follow below in full width.
    """
    blocks = []

    # Create a two-column layout
    blocks.append({
        "type": "column_list",
        "column_list": {
            "children": [
                # Left column - Ingredients
                {
                    "type": "column",
                    "column": {
                        "children": [
                            {
                                "type": "heading_2",
                                "heading_2": {
                                    "rich_text": [{
                                        "type": "text",
                                        "text": {"content": "Ingredients"}
                                    }],
                                    "color": "default",
                                    "is_toggleable": False
                                }
                            }
                        ]
                    }
                },
                # Right column - Yield and Nutrition
                {
                    "type": "column",
                    "column": {
                        "children": []
                    }
                }
            ]
        }
    })

    # Add ingredients to left column
    left_column = blocks[0]["column_list"]["children"][0]["column"]["children"]
    if recipe_data.get('ingredients'):
        for ingredient in recipe_data['ingredients']:
            left_column.append({
                "type": "to_do",
                "to_do": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": ingredient.strip()}
                    }],
                    "checked": False,
                    "color": "default"
                }
            })

    # Add yield and nutrition to right column
    right_column = blocks[0]["column_list"]["children"][1]["column"]["children"]

    # Add recipe yield/servings if available
    if recipe_data.get('yields'):
        right_column.append({
            "type": "callout",
            "callout": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": f"Yield: {recipe_data['yields']}"}
                }],
                "color": "blue",
                "icon": {"emoji": "🍳"}
            }
        })

    # Add nutrition information if available
    if recipe_data.get('nutrients'):
        right_column.extend([
            {
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": "Nutrition"}
                    }],
                    "color": "default",
                    "is_toggleable": False
                }
            }
        ])

        # Nutrition label mapping and order
        nutrition_mapping = {
            'calories': 'Calories',
            'carbohydrateContent': 'Carbs',
            'proteinContent': 'Protein',
            'fatContent': 'Fat',
            'unsaturatedFatContent': 'Unsat Fat',
            'saturatedFatContent': 'Sat Fat',
            'fiberContent': 'Fiber',
            'sugarContent': 'Sugar',
            'sodiumContent': 'Sodium',
            'cholesterolContent': 'Cholesterol',
            'servingSize': 'Serving Size'
        }

        # Format nutrition information in specified order
        nutrition_lines = []
        for key in nutrition_mapping:
            if key in recipe_data['nutrients']:
                value = recipe_data['nutrients'][key]
                label = nutrition_mapping[key]
                nutrition_lines.append(f"{label}: {value}")

        if nutrition_lines:
            right_column.append({
                "type": "callout",
                "callout": {
                    "rich_text": [{
                        "type": "text",
                        "text": {
                            "content": "\n".join(nutrition_lines)
                        }
                    }],
                    "color": "green",
                    "icon": {"emoji": "🥗"}
                }
            })

    # Add divider before instructions
    blocks.append({
        "type": "divider",
        "divider": {}
    })

    # Add instructions section with numbered list
    if recipe_data.get('instructions'):
        blocks.extend([
            {
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": "Instructions"}
                    }],
                    "color": "default",
                    "is_toggleable": False
                }
            }
        ])

        # Add each instruction step as a numbered list item
        for step in recipe_data['instructions']:
            if isinstance(step, str) and step.strip():
                blocks.append({
                    "type": "numbered_list_item",
                    "numbered_list_item": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": step.strip()}
                        }],
                        "color": "default"
                    }
                })

    return blocks

def update_notion_page(page_id: str, recipe_data: Dict[str, Any]) -> None:
    """
    Update a Notion page with recipe data.
    Required fields: title, host
    Optional fields: url, total_time, prep_time, cuisine, category
    """
    if not notion:
        raise ValueError("Notion client not initialized. Please set NOTION_API_KEY environment variable.")

    # Validate required fields
    if not recipe_data.get("title") or not recipe_data.get("host"):
        raise ValueError("Recipe data must include title and host")

    # Create properties object with required fields
    properties = {
        "Name": {"title": [{"text": {"content": recipe_data["title"]}}]},
        "Source": {"rich_text": [{"text": {"content": recipe_data["host"]}}]},
    }

    # Add URL if available
    if recipe_data.get("url"):
        properties["Link"] = {"url": recipe_data["url"]}

    # Add optional time properties if they are numbers
    if isinstance(recipe_data.get('total_time'), (int, float)):
        properties["Cooking Time, total"] = {"number": float(recipe_data["total_time"])}
    if isinstance(recipe_data.get('prep_time'), (int, float)):
        properties["Preparation Time"] = {"number": float(recipe_data["prep_time"])}

    # Handle cuisine/tags if available
    if recipe_data.get('cuisine'):
        try:
            # Convert cuisine to list if it's a string and clean up the tags
            cuisines = recipe_data['cuisine']
            if isinstance(cuisines, str):
                # Split by comma and clean each tag
                cuisines = [tag.strip() for tag in cuisines.split(',')]
            elif not isinstance(cuisines, list):
                cuisines = [str(cuisines)]

            # Cuisine emoji mapping
            cuisine_emojis = {
                'Mexican': '🇲🇽 Mexican',
                'Italian': '🇮🇹 Italian',
                'American': '🇺🇸 American',
                'Japanese': '🇯🇵 Japanese',
                'Chinese': '🇨🇳 Chinese',
                'Indian': '🇮🇳 Indian',
                'Thai': '🇹🇭 Thai',
                'Vietnamese': '🇻🇳 Vietnamese',
                'French': '🇫🇷 French',
                'Spanish': '🇪🇸 Spanish',
                'Greek': '🇬🇷 Greek',
                'Korean': '🇰🇷 Korean',
                'Mediterranean': '🌊 Mediterranean',
                'Middle Eastern': '🕌 Middle Eastern',
                'Caribbean': '🌴 Caribbean',
                'Texmex': '🌮 Tex-Mex',
                'Bbq': '🍖 BBQ',
                'Barbecue': '🍖 BBQ',
                'Asian': '🥢 Asian',
                'European': '🇪🇺 European',
                'African': '🌍 African',
                'Brazilian': '🇧🇷 Brazilian',
                'Hawaiian': '🌺 Hawaiian',
                'Southern': '🍗 Southern',
                'Cajun': '🦐 Cajun',
                'Creole': '🦐 Creole',
                'Soul Food': '🍗 Soul Food',
                'Vegetarian': '🥬 Vegetarian',
                'Vegan': '🌱 Vegan',
                'Fusion': '🔄 Fusion'
            }

            # Clean and capitalize each cuisine tag, add emojis where available
            cleaned_cuisines = []
            for tag in cuisines:
                if not tag or not isinstance(tag, str):
                    continue

                formatted_tag = tag.strip().title()
                # Check if we have an emoji mapping for this cuisine
                if formatted_tag in cuisine_emojis:
                    cleaned_cuisines.append(cuisine_emojis[formatted_tag])
                else:
                    cleaned_cuisines.append(formatted_tag)

            if cleaned_cuisines:
                properties["Tags"] = {"multi_select": [{"name": tag} for tag in cleaned_cuisines]}
        except Exception as e:
            logger.warning(f"Failed to process cuisine tags: {e}")

    # Handle meal type/category if available
    if recipe_data.get('category'):
        try:
            category = recipe_data['category']
            if isinstance(category, str) and category.strip():
                # If multiple categories, take the first one
                if ',' in category:
                    category = category.split(',')[0]
                # Clean and format the category
                formatted_category = category.strip().title()
                # Common variations mapping
                category_variations = {
                    'Main': '🍽️ Dinner',
                    'Main Dish': '🍽️ Dinner',
                    'Main Course': '🍽️ Dinner',
                    'Dinner': '🍽️ Dinner',
                    'Lunch': '🥪 Lunch',
                    'Breakfast': '🍳 Breakfast',
                    'Brunch': '🥞 Brunch',
                    'Side': '🥗 Side Dish',
                    'Side Dish': '🥗 Side Dish',
                    'Sides': '🥗 Side Dish',
                    'Starter': '🥄 Appetizer',
                    'Starters': '🥄 Appetizer',
                    'Appetizer': '🥄 Appetizer',
                    'Hors D\'Oeuvre': '🥄 Appetizer',
                    'Dessert': '🍰 Dessert',
                    'Desserts': '🍰 Dessert',
                    'Snack': '🍿 Snack',
                    'Snacks': '🍿 Snack',
                    'Drink': '🥤 Drink',
                    'Drinks': '🥤 Drink',
                    'Beverage': '🥤 Drink',
                    'Beverages': '🥤 Drink',
                    'Cocktail': '🍸 Cocktail',
                    'Cocktails': '🍸 Cocktail',
                    'Soup': '🥣 Soup',
                    'Soups': '🥣 Soup',
                    'Salad': '🥬 Salad',
                    'Salads': '🥬 Salad',
                    'Bread': '🍞 Bread',
                    'Breads': '🍞 Bread',
                    'Pasta': '🍝 Pasta',
                    'Noodles': '🍜 Noodles',
                    'Rice': '🍚 Rice',
                    'Sauce': '🥫 Sauce',
                    'Sauces': '🥫 Sauce',
                    'Dip': '🫕 Dip',
                    'Dips': '🫕 Dip',
                    'Marinade': '🧂 Marinade',
                    'Marinades': '🧂 Marinade',
                    'Grill': '🔥 Grill',
                    'Grilling': '🔥 Grill',
                    'Baking': '🥖 Baking',
                    'Seafood': '🦐 Seafood',
                    'Fish': '🐟 Fish',
                    'Meat': '🥩 Meat',
                    'Chicken': '🍗 Chicken',
                    'Beef': '🥩 Beef',
                    'Pork': '🥓 Pork',
                    'Lamb': '🐑 Lamb'
                }
                # Use mapped version if it exists, otherwise use formatted version
                final_category = category_variations.get(formatted_category, formatted_category)
                # Ensure category length is within Notion's limit (100 characters)
                if len(final_category) > 100:
                    final_category = final_category[:97] + "..."
                properties["Type"] = {"select": {"name": final_category}}
        except Exception as e:
            logger.warning(f"Failed to process category: {e}")

    # First, update the page properties
    notion.pages.update(
        page_id=page_id,
        properties=properties
    )

    # Set cover image if available
    if recipe_data.get('image'):
        try:
            notion.pages.update(
                page_id=page_id,
                cover={
                    "type": "external",
                    "external": {
                        "url": recipe_data['image']
                    }
                }
            )
            logger.info("Successfully set cover image")
        except Exception as e:
            logger.warning(f"Failed to set cover image: {e}")

    # Then, get all existing blocks
    try:
        blocks = notion.blocks.children.list(block_id=page_id)

        # Delete all existing blocks
        for block in blocks.get('results', []):
            notion.blocks.delete(block_id=block['id'])

        logger.info(f"Deleted {len(blocks.get('results', []))} existing blocks")
    except Exception as e:
        logger.warning(f"Error cleaning up existing blocks: {e}")

    # Finally, add the new content blocks
    try:
        notion.blocks.children.append(
            block_id=page_id,
            children=create_notion_blocks(recipe_data)
        )
        logger.info("Successfully added new content blocks")
    except Exception as e:
        logger.error(f"Error adding content blocks: {e}")
        raise

def lambda_handler(event, context):
    """
    Main Lambda handler function.
    """
    try:
        logger.info("Starting Lambda execution")
        logger.debug(f"Received event: {json.dumps(event)}")

        # Extract page info from the event
        page_info = extract_notion_page_info(event)
        if not page_info:
            raise ValueError("Failed to extract page info from event")

        # Unpack the tuple
        page_id, url = page_info

        if not url or not page_id:
            raise ValueError(f"Missing required fields. URL: {url}, Page ID: {page_id}")

        if not is_valid_url(url):
            raise ValueError(f"Invalid URL format: {url}")

        # Scrape recipe data
        recipe_data = scrape_recipe(url)
        if not recipe_data:
            raise ValueError("Failed to scrape recipe data")

        # Update Notion page
        update_notion_page(page_id, recipe_data)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully processed recipe',
                'page_id': page_id,
                'url': url
            })
        }

    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': str(e)
            })
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal server error'
            })
        }
