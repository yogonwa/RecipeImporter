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
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import extruct
from w3lib.html import get_base_url

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configure requests session with retries and headers
def create_requests_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    return session

# Use the session for requests
session = create_requests_session()

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

def create_import_details_block(recipe_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a collapsible import details block showing how each field was parsed.
    Includes confidence score and parsing methods for each field.
    
    Args:
        recipe_data: Dictionary containing recipe data, parsing methods, and confidence score
    """
    # Get confidence score and determine confidence level
    confidence_score = recipe_data.get("confidence_score", 0.0)
    if confidence_score >= 0.8:
        confidence_emoji = "🟢"  # High confidence
        confidence_text = "High Confidence"
    elif confidence_score >= 0.6:
        confidence_emoji = "🟡"  # Medium confidence
        confidence_text = "Medium Confidence"
    elif confidence_score >= 0.4:
        confidence_emoji = "🟠"  # Low confidence
        confidence_text = "Low Confidence"
    else:
        confidence_emoji = "🔴"  # Poor confidence
        confidence_text = "Poor Confidence"

    # Create the details text with confidence score header
    details_text = f"Confidence Score: {confidence_emoji} {confidence_score:.2f} ({confidence_text})\n\n"
    details_text += "Parsing Methods:\n"

    # Add parsing method for each field with emojis
    method_emojis = {
        "schema.org": "✨",  # Best source
        "wild_mode": "🔍",   # Good source
        "llm": "🤖",        # AI fallback
        "NOT_FOUND": "❌",   # Not found
        "ERROR": "⚠️"       # Error occurred
    }

    # Group fields by their source
    fields_by_source = {}
    parsing_methods = recipe_data.get("parsing_methods", {})
    
    for field, method in parsing_methods.items():
        if field != "all_fields":  # Skip the all_fields entry
            if method not in fields_by_source:
                fields_by_source[method] = []
            fields_by_source[method].append(field)

    # Add fields grouped by source
    for method in ["schema.org", "wild_mode", "llm", "NOT_FOUND", "ERROR"]:
        if method in fields_by_source:
            emoji = method_emojis.get(method, "")
            fields = fields_by_source[method]
            details_text += f"\n{emoji} {method}:\n"
            for field in sorted(fields):
                details_text += f"  • {field}\n"

    # Add warning if present
    if "warning" in recipe_data:
        details_text += f"\n⚠️ Warning: {recipe_data['warning']}\n"

    # Add timestamp
    details_text += f"\n🕒 Parsed: {recipe_data.get('parse_timestamp', 'Unknown time')}"
    
    return {
        "type": "toggle",
        "toggle": {
            "rich_text": [{
                "type": "text",
                "text": {"content": f"🔍 Import Details ({confidence_emoji} {confidence_score:.2f})"}
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

def calculate_confidence_score(recipe_data: Dict[str, Any]) -> float:
    """
    Calculate a confidence score (0-1) for the recipe data quality.
    
    Scoring weights:
    - Required fields (0.7 total):
      * Title: 0.2
      * Ingredients: 0.25
      * Instructions: 0.25
    - Optional fields (0.3 total):
      * Image: 0.1
      * Time/Yield: 0.1
      * Cuisine/Category: 0.05
      * Nutrients: 0.05
    
    Source quality multipliers:
    - schema.org: 1.0 (highest - official recipe-scrapers)
    - json-ld: 0.9 (high - direct structured data)
    - wild_mode: 0.7 (medium - pattern matching)
    - llm: 0.5 (lowest - AI extraction)
    """
    score = 0.0
    parsing_methods = recipe_data.get("parsing_methods", {})
    
    # Required fields scoring
    required_weights = {
        "title": 0.20,
        "ingredients": 0.25,
        "instructions": 0.25
    }
    
    # Optional fields scoring
    optional_weights = {
        "image": 0.10,
        "total_time": 0.05,
        "yields": 0.05,
        "cuisine": 0.025,
        "category": 0.025,
        "nutrients": 0.05
    }
    
    # Source quality multipliers
    source_multipliers = {
        "schema.org": 1.0,  # Highest - official recipe-scrapers
        "json-ld": 0.9,    # High - direct structured data
        "wild_mode": 0.7,  # Medium - pattern matching
        "llm": 0.5,        # Lowest - AI extraction
        "NOT_FOUND": 0.0,
        "ERROR": 0.0
    }
    
    # Score required fields
    for field, weight in required_weights.items():
        if field in recipe_data and recipe_data[field]:
            source = parsing_methods.get(field, "ERROR")
            multiplier = source_multipliers.get(source, 0.5)
            score += weight * multiplier
    
    # Score optional fields
    for field, weight in optional_weights.items():
        if field in recipe_data and recipe_data[field]:
            source = parsing_methods.get(field, "ERROR")
            multiplier = source_multipliers.get(source, 0.5)
            score += weight * multiplier
    
    return round(score, 2)

def try_standard_scraping(url: str) -> Dict[str, Any]:
    """
    Attempt to scrape recipe using recipe-scrapers' standard mode (Schema.org JSON-LD).
    Returns recipe data with parsing methods or None if failed.
    """
    try:
        scraper = scrape_me(url)
        
        # Track which fields were found and their sources
        parsing_methods = {}
        recipe_data = {
            "url": url,
            "host": scraper.host(),
            "parsing_methods": parsing_methods,
            "parse_timestamp": datetime.now().isoformat()
        }
        
        # Required fields - must have these for valid recipe
        required_fields = {
            "title": scraper.title,
            "ingredients": scraper.ingredients,
            "instructions": scraper.instructions
        }
        
        # Optional fields - nice to have but not required
        optional_fields = {
            "total_time": scraper.total_time,
            "yields": scraper.yields,
            "image": scraper.image,
            "nutrients": scraper.nutrients,
            "cuisine": scraper.cuisine,
            "category": scraper.category
        }
        
        # Check required fields
        missing_required = []
        for field, method in required_fields.items():
            try:
                value = method()
                if value:
                    recipe_data[field] = value
                    parsing_methods[field] = "schema.org"
                else:
                    missing_required.append(field)
            except Exception as e:
                missing_required.append(field)
                logger.warning(f"Failed to extract required field {field}: {str(e)}")
        
        # Check optional fields
        for field, method in optional_fields.items():
            try:
                value = method()
                if value:
                    recipe_data[field] = value
                    parsing_methods[field] = "schema.org"
                else:
                    parsing_methods[field] = "NOT_FOUND"
            except Exception as e:
                parsing_methods[field] = "ERROR"
                logger.warning(f"Failed to extract optional field {field}: {str(e)}")
        
        # Calculate confidence score
        recipe_data["confidence_score"] = calculate_confidence_score(recipe_data)
        
        # If any required fields are missing, return partial data for fallback
        if missing_required:
            recipe_data["missing_required"] = missing_required
            return recipe_data
            
        return recipe_data
        
    except Exception as e:
        logger.error(f"Standard scraping failed: {str(e)}")
        return None

def try_wild_mode_scraping(url: str) -> Dict[str, Any]:
    """
    Attempt to scrape recipe using recipe-scrapers' wild mode.
    Returns recipe data with parsing methods or None if failed.
    """
    try:
        # Create a new scraper instance without wild mode
        scraper = scrape_me(url)
        
        # Enable wild mode through the wild_mode property
        scraper.wild_mode = True
        
        # Track which fields were found and their sources
        parsing_methods = {}
        recipe_data = {
            "url": url,
            "host": scraper.host(),
            "parsing_methods": parsing_methods,
            "parse_timestamp": datetime.now().isoformat()
        }
        
        # Try to extract all fields using wild mode
        field_methods = {
            "title": scraper.title,
            "ingredients": scraper.ingredients,
            "instructions": scraper.instructions,
            "total_time": scraper.total_time,
            "yields": scraper.yields,
            "image": scraper.image,
            "nutrients": scraper.nutrients,
            "cuisine": scraper.cuisine,
            "category": scraper.category
        }
        
        for field, method in field_methods.items():
            try:
                value = method()
                if value:
                    recipe_data[field] = value
                    parsing_methods[field] = "wild_mode"
            except Exception as e:
                parsing_methods[field] = "NOT_FOUND"
                logger.warning(f"Wild mode failed to extract {field}: {str(e)}")
        
        # Calculate confidence score
        recipe_data["confidence_score"] = calculate_confidence_score(recipe_data)
        
        return recipe_data
        
    except Exception as e:
        logger.error(f"Wild mode scraping failed: {str(e)}")
        return None

def extract_json_ld(url: str) -> Optional[Dict[str, Any]]:
    """
    Directly extract JSON-LD recipe data from a webpage.
    Falls back to this when recipe-scrapers fails.
    """
    try:
        # Fetch the webpage
        response = session.get(url, timeout=10)
        response.raise_for_status()
        html_content = response.text
        
        logger.info(f"Successfully fetched content from {url}")
        
        # Extract all structured data
        base_url = get_base_url(html_content, response.url)
        data = extruct.extract(html_content, base_url=base_url, syntaxes=['json-ld'])
        
        logger.info(f"Found {len(data.get('json-ld', []))} JSON-LD blocks")
        
        # Look for recipe data in JSON-LD
        if 'json-ld' in data and data['json-ld']:
            for json_ld_block in data['json-ld']:
                # Check if we have a @graph array
                if '@graph' in json_ld_block:
                    logger.info("Found @graph array in JSON-LD")
                    for item in json_ld_block['@graph']:
                        if isinstance(item, dict) and item.get('@type') in ['Recipe', 'schema:Recipe']:
                            logger.info("Found Recipe schema in @graph")
                            return process_recipe_schema(item, url)
                # Check if this block itself is a Recipe
                elif isinstance(json_ld_block, dict) and json_ld_block.get('@type') in ['Recipe', 'schema:Recipe']:
                    logger.info("Found Recipe schema in root")
                    return process_recipe_schema(json_ld_block, url)
                    
        logger.warning("No Recipe schema found in JSON-LD data")
        return None
        
    except Exception as e:
        logger.error(f"JSON-LD extraction failed: {str(e)}")
        return None

def process_recipe_schema(item: Dict[str, Any], url: str) -> Dict[str, Any]:
    """
    Process a Recipe schema and convert it to our internal format.
    """
    recipe_data = {
        "url": url,
        "host": urlparse(url).netloc,
        "parsing_methods": {},
        "parse_timestamp": datetime.now().isoformat()
    }
    
    # Map required fields
    if 'name' in item:
        recipe_data['title'] = item['name']
        recipe_data['parsing_methods']['title'] = 'json-ld'
    
    if 'recipeIngredient' in item:
        recipe_data['ingredients'] = item['recipeIngredient']
        recipe_data['parsing_methods']['ingredients'] = 'json-ld'
    
    if 'recipeInstructions' in item:
        # Handle both string and structured instructions
        instructions = []
        for instruction in item['recipeInstructions']:
            if isinstance(instruction, str):
                instructions.append(instruction)
            elif isinstance(instruction, dict) and 'text' in instruction:
                instructions.append(instruction['text'])
        recipe_data['instructions'] = instructions if instructions else item['recipeInstructions']
        recipe_data['parsing_methods']['instructions'] = 'json-ld'
    
    # Map optional fields
    if 'image' in item:
        recipe_data['image'] = item['image'][0] if isinstance(item['image'], list) else item['image']
        recipe_data['parsing_methods']['image'] = 'json-ld'
    
    if 'totalTime' in item:
        try:
            # Convert ISO duration to minutes
            from isodate import parse_duration
            duration = parse_duration(item['totalTime'])
            recipe_data['total_time'] = duration.total_seconds() / 60
            recipe_data['parsing_methods']['total_time'] = 'json-ld'
        except Exception as e:
            logger.warning(f"Failed to parse totalTime: {e}")
    
    if 'recipeYield' in item:
        recipe_data['yields'] = item['recipeYield']
        recipe_data['parsing_methods']['yields'] = 'json-ld'
    
    if 'recipeCuisine' in item:
        recipe_data['cuisine'] = item['recipeCuisine']
        recipe_data['parsing_methods']['cuisine'] = 'json-ld'
    
    if 'recipeCategory' in item:
        recipe_data['category'] = item['recipeCategory']
        recipe_data['parsing_methods']['category'] = 'json-ld'
    
    if 'nutrition' in item:
        nutrition = item['nutrition']
        recipe_data['nutrients'] = {
            key.replace('Content', ''): value 
            for key, value in nutrition.items() 
            if key.endswith('Content')
        }
        recipe_data['parsing_methods']['nutrients'] = 'json-ld'
    
    # Calculate confidence score
    recipe_data['confidence_score'] = calculate_confidence_score(recipe_data)
    
    return recipe_data

def scrape_recipe(url: str) -> Dict[str, Any]:
    """
    Scrape recipe data with multiple fallback methods and confidence thresholds.
    """
    try:
        best_data = None
        best_score = 0.0
        
        # Step 1: Try standard scraping (Schema.org JSON-LD via recipe-scrapers)
        recipe_data = try_standard_scraping(url)
        
        if recipe_data:
            score = recipe_data["confidence_score"]
            if score >= 0.8:  # High confidence threshold
                logger.info(f"High confidence recipe data (score: {score}) from Schema.org")
                return recipe_data
            
            best_data = recipe_data
            best_score = score
        
        # Step 2: Try direct JSON-LD extraction if recipe-scrapers failed
        if not best_data or best_score < 0.8:
            logger.info("Attempting direct JSON-LD extraction")
            json_ld_data = extract_json_ld(url)
            
            if json_ld_data:
                score = json_ld_data["confidence_score"]
                if score >= 0.8:  # High confidence threshold
                    logger.info(f"High confidence recipe data (score: {score}) from direct JSON-LD")
                    return json_ld_data
                
                if not best_data or score > best_score:
                    best_data = json_ld_data
                    best_score = score
        
        # Step 3: Try wild mode scraping
        wild_data = try_wild_mode_scraping(url)
        
        if wild_data:
            # If we have previous data, try to merge and improve score
            if best_data:
                # Merge wild mode data into best_data where missing
                for field, value in wild_data.items():
                    if field not in best_data or not best_data[field]:
                        best_data[field] = value
                        best_data["parsing_methods"][field] = "wild_mode"
                
                # Recalculate confidence score after merge
                best_data["confidence_score"] = calculate_confidence_score(best_data)
                
                if best_data["confidence_score"] >= 0.6:  # Medium confidence threshold
                    logger.info(f"Medium confidence recipe data (score: {best_data['confidence_score']}) from merged sources")
                    return best_data
            else:
                best_data = wild_data
                best_score = wild_data["confidence_score"]
        
        # Step 4: Try LLM extraction if confidence is still low
        if not best_data or best_score < 0.4:  # Low confidence threshold
            logger.info("Low confidence in current data, attempting LLM extraction")
            try:
                response = session.get(url, timeout=10)
                response.raise_for_status()
                html_content = response.text
                llm_data = extract_recipe_with_gpt(html_content)
                
                if llm_data:
                    if best_data:
                        # Merge LLM data into best_data where missing
                        for field, value in llm_data.items():
                            if field not in best_data or not best_data[field]:
                                best_data[field] = value
                                best_data["parsing_methods"][field] = "llm"
                        
                        # Recalculate confidence score
                        best_data["confidence_score"] = calculate_confidence_score(best_data)
                    else:
                        best_data = llm_data
                        best_data["url"] = url
                        best_data["confidence_score"] = calculate_confidence_score(llm_data)
            except Exception as e:
                logger.error(f"Failed to fetch HTML content: {str(e)}")
        
        # Return best available data with confidence information
        if best_data:
            score = best_data["confidence_score"]
            if score < 0.4:
                best_data["warning"] = "Low confidence in extracted data"
            return best_data
        
        return {
            "error": "All extraction methods failed",
            "url": url,
            "confidence_score": 0.0
        }
        
    except Exception as e:
        logger.error(f"Recipe extraction failed: {str(e)}")
        return {
            "error": str(e),
            "url": url,
            "parse_timestamp": datetime.now().isoformat(),
            "parsing_methods": {"all_fields": "ERROR"},
            "confidence_score": 0.0
        }

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

        # Format nutrition information
        nutrition_lines = []
        for key, value in recipe_data['nutrients'].items():
            nutrition_lines.append(f"{key}: {value}")

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

        # Split instructions into steps if it's a string
        if isinstance(recipe_data['instructions'], str):
            # Split on newlines and filter out empty lines
            steps = [step.strip() for step in recipe_data['instructions'].split('\n') if step.strip()]
        else:
            steps = recipe_data['instructions']

        # Add each instruction step as a numbered list item
        for step in steps:
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

    # Add divider before import details
    blocks.append({
        "type": "divider",
        "divider": {}
    })

    # Add import details block
    blocks.append(create_import_details_block(recipe_data))

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

    # Create content blocks
    content_blocks = create_notion_blocks(recipe_data)

    # Split blocks into chunks of 100
    def chunk_blocks(blocks, size=100):
        return [blocks[i:i + size] for i in range(0, len(blocks), size)]

    # Add blocks in chunks
    try:
        for chunk in chunk_blocks(content_blocks):
            notion.blocks.children.append(
                block_id=page_id,
                children=chunk
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
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Failed to extract page info from event'
                })
            }

        # Unpack the tuple
        page_id, url = page_info

        if not url or not page_id:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f'Missing required fields. URL: {url}, Page ID: {page_id}'
                })
            }

        if not is_valid_url(url):
            # Create Notion page with invalid URL error
            error_data = {
                "title": "Invalid URL",
                "host": url,
                "url": url,
                "parse_timestamp": datetime.now().isoformat(),
                "parsing_methods": {"all_fields": "ERROR"},
                "confidence_score": 0.0,
                "error": f"Invalid URL format: {url}"
            }
            update_notion_page(page_id, error_data)
            return {
                'statusCode': 200,  # Return success since we updated Notion
                'body': json.dumps({
                    'message': 'Created error page in Notion',
                    'page_id': page_id,
                    'url': url
                })
            }

        # Attempt to scrape recipe data
        recipe_data = scrape_recipe(url)
        
        # Even if scraping failed, we'll update the Notion page with what we have
        if not recipe_data:
            recipe_data = {
                "title": "Recipe Parsing Failed",
                "host": url,
                "url": url,
                "parse_timestamp": datetime.now().isoformat(),
                "parsing_methods": {"all_fields": "ERROR"},
                "confidence_score": 0.0,
                "error": "Failed to extract any recipe data"
            }

        # Update Notion page with whatever data we have (success or failure)
        update_notion_page(page_id, recipe_data)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully processed recipe',
                'page_id': page_id,
                'url': url,
                'confidence_score': recipe_data.get('confidence_score', 0.0)
            })
        }

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        try:
            # Try to create an error page in Notion
            error_data = {
                "title": "Processing Error",
                "host": url if 'url' in locals() else "Unknown",
                "url": url if 'url' in locals() else "Unknown",
                "parse_timestamp": datetime.now().isoformat(),
                "parsing_methods": {"all_fields": "ERROR"},
                "confidence_score": 0.0,
                "error": f"Internal error: {str(e)}"
            }
            if 'page_id' in locals():
                update_notion_page(page_id, error_data)
        except Exception as notion_error:
            logger.error(f"Failed to create error page in Notion: {str(notion_error)}")

        return {
            'statusCode': 200,  # Return success since we tried our best
            'body': json.dumps({
                'message': 'Created error page in Notion',
                'error': str(e)
            })
        }
