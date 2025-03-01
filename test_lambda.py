import os
import json
from lambda_function import lambda_handler

# Test recipe URL - using a reliable recipe site
TEST_URL = "https://www.allrecipes.com/recipe/228122/curry-stand-chicken-tikka-masala-sauce/"

# Simulate Notion webhook event
test_event = {
    "body": json.dumps({
        "page": {
            "id": "test_page_id",
            "properties": {
                "Link": {
                    "rich_text": [
                        {
                            "text": {
                                "content": TEST_URL
                            }
                        }
                    ]
                }
            }
        }
    })
}

def test_lambda():
    """
    Test the Lambda function with a real recipe URL.
    """
    print("🧪 Starting Lambda function test...")
    print(f"🔗 Testing with URL: {TEST_URL}")
    
    # Verify environment variables
    notion_key = os.environ.get('NOTION_API_KEY')
    notion_db = os.environ.get('NOTION_DATABASE_ID')
    
    if not notion_key or not notion_db:
        print("❌ Error: Missing environment variables!")
        print("Please set NOTION_API_KEY and NOTION_DATABASE_ID")
        return
    
    try:
        # Call lambda handler
        print("📡 Calling Lambda handler...")
        response = lambda_handler(test_event, None)
        
        # Check response
        if response['statusCode'] == 200:
            print("✅ Test passed! Recipe was successfully processed")
            print("\nResponse details:")
            print(f"Status Code: {response['statusCode']}")
            print(f"Body: {json.loads(response['body'])}")
        else:
            print("❌ Test failed!")
            print(f"Status Code: {response['statusCode']}")
            print(f"Error: {response['body']}")
            
    except Exception as e:
        print(f"❌ Test failed with exception: {str(e)}")

if __name__ == "__main__":
    test_lambda() 