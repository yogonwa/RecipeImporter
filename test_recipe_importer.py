import json
import os
from lambda_function import scrape_recipe, update_notion_page, lambda_handler

def test_scraping():
    """Test recipe scraping from different sources"""
    test_urls = [
        "https://www.allrecipes.com/recipe/10813/best-chocolate-chip-cookies/",  # Popular, likely stable URL
        "https://www.simplyrecipes.com/recipes/perfect_guacamole/",  # SimplyRecipes works well
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

def test_notion_integration():
    """Test Notion integration with a test page"""
    # Check if we have the required environment variables
    if not os.environ.get('NOTION_API_KEY'):
        print("\n✗ NOTION_API_KEY not set. Skipping Notion integration test.")
        return
    
    print("\n=== Testing Notion Integration ===")
    
    # Create a mock webhook event with a known working URL
    test_event = {
        "body": json.dumps({
            "page": {
                "id": os.environ.get('TEST_PAGE_ID'),
                "properties": {
                    "Link": {
                        "rich_text": [{
                            "text": {
                                "content": "https://www.simplyrecipes.com/recipes/perfect_guacamole/"
                            }
                        }]
                    }
                }
            }
        })
    }
    
    if not os.environ.get('TEST_PAGE_ID'):
        print("✗ TEST_PAGE_ID not set. Please set it to test Notion integration.")
        print("  Create a page in your Notion database and set its ID as TEST_PAGE_ID")
        return
    
    try:
        print(f"Using Notion API Key: {os.environ.get('NOTION_API_KEY')[:10]}...")
        print(f"Using Test Page ID: {os.environ.get('TEST_PAGE_ID')}")
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

def main():
    print("Starting Recipe Importer Tests...")
    
    # Test recipe scraping
    test_scraping()
    
    # Test Notion integration
    test_notion_integration()
    
    print("\nTests completed!")

if __name__ == "__main__":
    main() 