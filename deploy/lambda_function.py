import json
import logging
import os
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse
from recipe_scrapers import scrape_me
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode
from notion_client import Client
from notion_client.errors import APIResponseError

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

def extract_notion_page_info(event: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """
    Extract page ID and URL from Notion webhook event.
    Returns tuple of (page_id, url) if valid, None if invalid.
    """
    try:
        # Parse body
        body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        
        # Extract page ID and properties from the webhook payload
        page_id = body.get('page', {}).get('id')
        properties = body.get('page', {}).get('properties', {})
        
        # Get URL from properties (using 'Link' field as per schema)
        url = properties.get('Link', {}).get('rich_text', [{}])[0].get('text', {}).get('content', '')
        
        if not page_id or not url:
            logger.error("Missing page ID or URL in webhook payload")
            return None
            
        if not is_valid_url(url):
            logger.error(f"Invalid URL format: {url}")
            return None
            
        return (page_id, url)
        
    except Exception as e:
        logger.error(f"Error extracting page info: {str(e)}")
        return None

def scrape_recipe(url: str) -> Dict[str, Any]:
    """
    Scrape recipe data from the provided URL.
    Returns structured recipe data.
    """
    try:
        scraper = scrape_me(url)
        
        recipe_data = {
            "title": scraper.title(),
            "total_time": scraper.total_time(),
            "prep_time": scraper.prep_time() if hasattr(scraper, 'prep_time') else None,
            "yields": scraper.yields(),
            "ingredients": scraper.ingredients(),
            "instructions": scraper.instructions().split('. ') if scraper.instructions() else [],
            "image": scraper.image(),
            "host": scraper.host(),
            "nutrients": scraper.nutrients(),
            "cuisine": scraper.cuisine() if hasattr(scraper, 'cuisine') else None,
            "category": scraper.category() if hasattr(scraper, 'category') else None,
            "url": url
        }
        
        # Filter out None values
        filtered_data = {k: v for k, v in recipe_data.items() if v is not None}
        
        # Ensure we have at least some basic recipe data
        if not filtered_data.get('title') or not filtered_data.get('ingredients'):
            raise NoSchemaFoundInWildMode("Could not extract basic recipe information")
        
        return filtered_data
    
    except WebsiteNotImplementedError:
        logger.warning(f"Website not implemented for URL: {url}")
        raise
    except NoSchemaFoundInWildMode:
        logger.warning(f"No recipe schema found for URL: {url}")
        raise
    except Exception as e:
        logger.error(f"Scraping error: {str(e)}")
        raise

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

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler function.
    """
    try:
        # Log the incoming event
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Extract page info from the webhook
        page_info = extract_notion_page_info(event)
        if not page_info:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid webhook payload. Missing or invalid page ID or URL.'
                })
            }
        
        page_id, url = page_info
        
        # Scrape the recipe
        recipe_data = scrape_recipe(url)
        
        # Update the Notion page
        update_notion_page(page_id, recipe_data)
        
        # Return success response
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': True,
                'message': 'Recipe successfully scraped and page updated',
                'page_id': page_id,
                'data': recipe_data
            })
        }
        
    except (WebsiteNotImplementedError, NoSchemaFoundInWildMode) as e:
        return {
            'statusCode': 422,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': str(e),
                'message': 'Unable to extract recipe from the provided URL'
            })
        }
    except APIResponseError as e:
        return {
            'statusCode': 422,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Notion API Error',
                'message': str(e)
            })
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }
