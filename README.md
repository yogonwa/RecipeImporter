# Notion Recipe Importer

A Lambda function that automatically imports recipes from various recipe websites into your Notion database. The function scrapes recipe data and formats it into a clean, consistent layout in Notion.

## Features

- Scrapes recipes from supported recipe websites
- Creates formatted Notion pages with:
  - Two-column layout (ingredients and nutrition)
  - Checkbox list for ingredients
  - Numbered steps for instructions
  - Recipe metadata (cuisine, category, cooking time)
  - Cover images
  - Nutrition information
- Supports cuisine tags with country flag emojis
- Categorizes recipes with relevant emojis

## Setup

1. Clone this repository
2. Create a `.env` file with your credentials:
   ```
   NOTION_API_KEY=your_api_key
   NOTION_DATABASE_ID=your_database_id
   TEST_PAGE_ID=your_test_page_id
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Testing

Run the test script:
```bash
./run_tests.sh
```

## Deployment

TODO: Add deployment instructions for AWS Lambda and webhook setup

## Dependencies

- Python 3.8+
- recipe-scrapers
- notion-client
- python-dotenv

## Project Structure

```
notion_recipe_lambda/
├── lambda_function.py     # Main Lambda function
├── run_tests.sh          # Test script
├── requirements.txt      # Python dependencies
└── .env                 # Environment variables (not in repo)
```

## Next Steps

- [ ] Set up AWS Lambda deployment
- [ ] Configure webhook triggers
- [ ] Add error monitoring
- [ ] Expand recipe website support

## License

MIT 