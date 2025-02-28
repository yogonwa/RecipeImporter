import json
import requests
from notion_client import Client
from recipe_scrapers import scrape_me

# Notion API setup
NOTION_API_KEY = "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"  # Replace with your actual Notion API key
DATABASE_ID = "12cf9b70ee4e81928adcc78aa6848870"  # Replace with your actual Notion Database ID
notion = Client(auth=NOTION_API_KEY)

def lambda_handler(event, context):
    try:
        # Parse webhook payload from Zapier
        body = json.loads(event["body"])
        page_id = body.get("Page ID")
        url = body.get("Recipe URL")
        if not page_id or not url:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing Page ID or Recipe URL"})
            }
        
        # Extract recipe details
        scraper = scrape_me(url)
        recipe = {
            "title": scraper.title(),
            "source": scraper.host(),
            "tags": scraper.cuisine() or [],
            "type": scraper.category() or "",
            "cooking_time": scraper.total_time() or 0,
            "prep_time": scraper.prep_time() or 0,
            "ingredients": scraper.ingredients(),
            "instructions": scraper.instructions().split(". ")
        }
        
        # Update Notion entry
        notion.pages.update(
            page_id=page_id,
            properties={
                "Title": {"title": [{"text": {"content": recipe["title"]}}]},
                "Source": {"rich_text": [{"text": {"content": recipe["source"]}}]},
                "Tags": {"multi_select": [{"name": tag} for tag in recipe["tags"]]},
                "Type": {"select": {"name": recipe["type"]}},
                "Cooking Time": {"number": recipe["cooking_time"]},
                "Prep Time": {"number": recipe["prep_time"]},
            },
            children=[
                {"object": "block", "type": "heading_2", "heading_2": {"text": [{"text": {"content": "Ingredients"}}]}},
            ] + [
                {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"text": [{"text": {"content": ingredient}}]} }
                for ingredient in recipe["ingredients"]
            ] + [
                {"object": "block", "type": "heading_2", "heading_2": {"text": [{"text": {"content": "Instructions"}}]}},
            ] + [
                {"object": "block", "type": "numbered_list_item", "numbered_list_item": {"text": [{"text": {"content": step}}]} }
                for step in recipe["instructions"]
            ]
        )
        
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Recipe successfully added to Notion."})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
