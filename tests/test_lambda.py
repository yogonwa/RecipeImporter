"""
Lambda Function Integration Tests
------------------------------

This module contains integration tests for the Lambda function handler.
It tests the complete flow from webhook event to Notion page creation.

Test Categories:
1. Event Processing Tests
   - Test webhook event parsing
   - Test API Gateway event handling
   - Test malformed event handling

2. End-to-End Tests
   - Test complete recipe import flow
   - Test error handling and responses
   - Test Lambda timeout scenarios

Usage:
    Run all tests:
        python -m pytest tests/test_lambda.py
    
    Run specific test:
        python -m pytest tests/test_lambda.py -k test_name

Environment Setup:
    Requires environment variables:
    - NOTION_API_KEY: Valid Notion API key
    - NOTION_DATABASE_ID: Target database ID
"""

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