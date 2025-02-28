import json
from lambda_function import lambda_handler, scrape_recipe

def test_direct_scrape():
    """Test the scrape_recipe function directly"""
    # Test URLs - using well-supported recipe websites
    test_urls = [
        "https://www.allrecipes.com/recipe/273864/greek-chicken-skewers/",
        "https://www.bbcgoodfood.com/recipes/classic-lasagne-0",
        "https://www.epicurious.com/recipes/food/views/classic-chocolate-mousse-107701",
    ]
    
    for url in test_urls:
        print(f"\nTesting URL: {url}")
        try:
            result = scrape_recipe(url)
            print("Success! Recipe data:")
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")

def test_lambda_handler():
    """Test the full Lambda handler with a mock event"""
    # Test event simulating API Gateway request
    test_event = {
        "body": json.dumps({
            "url": "https://www.allrecipes.com/recipe/273864/greek-chicken-skewers/"
        })
    }
    
    print("\nTesting Lambda handler with mock event:")
    result = lambda_handler(test_event, None)
    print(f"Status Code: {result['statusCode']}")
    print("Response Body:")
    print(json.dumps(json.loads(result['body']), indent=2))

if __name__ == "__main__":
    print("=== Testing Direct Scraping ===")
    test_direct_scrape()
    
    print("\n=== Testing Lambda Handler ===")
    test_lambda_handler() 