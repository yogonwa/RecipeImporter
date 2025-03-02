import json
import os
from lambda_function import scrape_recipe, update_notion_page, lambda_handler, get_page_id_from_unique_id

def test_scraping():
    """Test recipe scraping from different sources"""
    test_urls = [
        "https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/",  # Popular, likely stable URL
        "https://www.simplyrecipes.com/recipes/perfect_guacamole/",  # SimplyRecipes works well
        "https://www.foodnetwork.com/recipes/food-network-kitchen/stuffed-green-peppers-3364195",
        "https://www.bonappetit.com/recipe/classic-chocolate-mousse"  # Bon Appetit usually works
    ]
    
    print("\n=== Testing Recipe Scraping ===")
    for url in test_urls:
        print(f"\nTesting URL: {url}")
        try:
            recipe_data = scrape_recipe(url)
            print("✓ Successfully scraped recipe:")
            print(f"  Title: {recipe_data.get('title')}")
            print(f"  Source: {recipe_data.get('host')}")
            print(f"  Cuisine: {recipe_data.get('cuisine')}")
            print(f"  Category: {recipe_data.get('category')}")
            print(f"  Total Time: {recipe_data.get('total_time')} minutes")
            print(f"  Number of Ingredients: {len(recipe_data.get('ingredients', []))}")
            print(f"  Number of Steps: {len(recipe_data.get('instructions', []))}")
        except Exception as e:
            print(f"✗ Error scraping {url}: {str(e)}")

def test_unique_id_lookup():
    """Test looking up a page ID from a unique ID"""
    print("\n=== Testing Unique ID Lookup ===")
    
    if not os.environ.get('NOTION_API_KEY') or not os.environ.get('NOTION_DATABASE_ID'):
        print("✗ NOTION_API_KEY or NOTION_DATABASE_ID not set. Skipping unique ID lookup test.")
        return
        
    test_unique_id = os.environ.get('TEST_UNIQUE_ID')
    if not test_unique_id:
        print("✗ TEST_UNIQUE_ID not set. Please set it to test unique ID lookup.")
        return
        
    try:
        page_id = get_page_id_from_unique_id(test_unique_id)
        if page_id:
            print(f"✓ Successfully found page ID: {page_id}")
        else:
            print("✗ Could not find page ID for the given unique ID")
    except Exception as e:
        print(f"✗ Error during unique ID lookup: {str(e)}")

def test_notion_integration():
    """Test Notion integration with a test page using unique ID"""
    if not os.environ.get('NOTION_API_KEY'):
        print("\n✗ NOTION_API_KEY not set. Skipping Notion integration test.")
        return
    
    print("\n=== Testing Notion Integration ===")
    
    # Create a mock webhook event with unique ID instead of page ID
    test_event = {
        "body": json.dumps({
            "properties": {
                "Unique ID": {"unique_id": {"number": 11}},
                "Link": {
                    "rich_text": [{
                        "text": {
                            "content": "https://www.simplyrecipes.com/recipes/perfect_guacamole/"
                        }
                    }]
                }
            }
        })
    }
    
    if not os.environ.get('TEST_UNIQUE_ID'):
        print("✗ TEST_UNIQUE_ID not set. Please set it to test Notion integration.")
        print("  Set the Unique ID from your Notion database as TEST_UNIQUE_ID")
        return
    
    try:
        print(f"Using Notion API Key: {os.environ.get('NOTION_API_KEY')[:10]}...")
        print(f"Using Test Unique ID: {os.environ.get('TEST_UNIQUE_ID')}")
        result = lambda_handler(test_event, None)
        if result['statusCode'] == 200:
            print("✓ Successfully updated Notion page")
            print(f"  Status Code: {result['statusCode']}")
            response_data = json.loads(result['body'])
            print(f"  Message: {response_data.get('message')}")
            print(f"  Recipe Title: {response_data.get('data', {}).get('title')}")
        else:
            print(f"✗ Error updating Notion page: {result['body']}")
    except Exception as e:
        print(f"✗ Error during Notion integration test: {str(e)}")
        import traceback
        print(traceback.format_exc())

def test_guacamole():
    """Test just the guacamole recipe integration"""
    print("\n=== Testing Guacamole Recipe Integration ===")
    
    if not os.environ.get('NOTION_API_KEY'):
        print("✗ NOTION_API_KEY not set. Skipping test.")
        return
        
    if not os.environ.get('TEST_UNIQUE_ID'):
        print("✗ TEST_UNIQUE_ID not set. Please set it to test integration.")
        return
        
    print(f"Using Notion API Key: {os.environ.get('NOTION_API_KEY')[:10]}...")
    print(f"Using Test Unique ID: {os.environ.get('TEST_UNIQUE_ID')}")
    
    # First test the unique ID lookup
    try:
        page_id = get_page_id_from_unique_id(os.environ.get('TEST_UNIQUE_ID'))
        if page_id:
            print(f"✓ Successfully found page ID: {page_id}")
        else:
            print("✗ Could not find page ID for the given unique ID")
            return
    except Exception as e:
        print(f"✗ Error during unique ID lookup: {str(e)}")
        return
    
    # Now test the recipe integration
    test_event = {
        "body": json.dumps({
            "properties": {
                "Unique ID": {"unique_id": {"number": int(os.environ.get('TEST_UNIQUE_ID').split('-')[1])}},
                "Link": {
                    "rich_text": [{
                        "text": {
                            "content": "https://www.simplyrecipes.com/recipes/perfect_guacamole/"
                        }
                    }]
                }
            }
        })
    }
    
    try:
        result = lambda_handler(test_event, None)
        if result['statusCode'] == 200:
            print("✓ Successfully updated Notion page")
            print(f"  Status Code: {result['statusCode']}")
            response_data = json.loads(result['body'])
            print(f"  Message: {response_data.get('message')}")
        else:
            print(f"✗ Error updating Notion page: {result['body']}")
    except Exception as e:
        print(f"✗ Error during recipe integration: {str(e)}")
        import traceback
        print(traceback.format_exc())

def main():
    print("Starting Guacamole Recipe Test...")
    test_guacamole()
    print("\nTest completed!")

if __name__ == "__main__":
    main() 