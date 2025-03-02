# Notion Recipe Importer

A serverless AWS Lambda function that imports recipes from various recipe websites into your Notion database, complete with ingredients, instructions, cooking times, and cuisine tags.

## Features

- 🔍 Supports 300+ recipe websites through recipe-scrapers
- 📝 Extracts detailed recipe information including:
  - Title and source
  - Ingredients and instructions
  - Cooking and prep times
  - Cuisine types with emoji tags
  - Recipe categories
  - Nutritional information (when available)
- 🎯 Creates well-formatted Notion pages with:
  - Two-column layout (ingredients and yield/nutrition)
  - Checkable ingredient lists
  - Numbered instructions
  - Cuisine tags with emojis
  - Recipe type categorization
- 🚀 Deployed as an AWS Lambda function
- 🔒 Secure handling of API keys through environment variables

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yogonwa/RecipeImporter.git
cd RecipeImporter
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```
NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_database_id
```

4. Build the Lambda deployment package:
```bash
chmod +x build.sh
./build.sh
```

## Deployment

1. Create a new Lambda function in AWS:
   - Runtime: Python 3.9
   - Architecture: x86_64
   - Memory: 256 MB (recommended)
   - Timeout: 30 seconds (recommended)

2. Upload the deployment package:
   - Upload `lambda_function.zip` to your Lambda function

3. Configure environment variables in Lambda:
   - Add `NOTION_API_KEY` and `NOTION_DATABASE_ID`

4. Set up API Gateway (TODO):
   - Create a new HTTP API
   - Configure Lambda integration
   - Set up security (API key, IAM, etc.)
   - Enable CORS if needed
   - Deploy the API

5. Configure Notion Webhook (TODO):
   - Set up webhook in your Notion integration
   - Configure webhook to trigger on page updates
   - Point webhook to your API Gateway endpoint
   - Test webhook connectivity

## Testing

Run the test script:
```bash
python test_lambda.py
```

## Recent Changes

- ✨ Added enhanced cuisine and category detection with emoji support
- 🐛 Fixed issues with recipe schema extraction
- 🔧 Improved error handling and logging
- 📦 Updated to recipe-scrapers 15.5.1
- 🐳 Added Docker-based deployment system
- 🧹 Cleaned up repository structure

## Next Steps

- [X] **PRIORITY:** Set up API Gateway integration
- [X] **PRIORITY:** Configure Notion webhook integration
- [ ] Add support for recipe images in Notion pages
- [ ] Implement rate limiting for recipe scraping
- [ ] Add support for custom cuisine/category mappings
- [ ] Create CloudFormation template for easier deployment
- [ ] Add integration tests for major recipe websites
- [ ] Set up CI/CD pipeline
- [ ] Add support for batch recipe imports
- [ ] Improve error reporting and notifications
- [ ] Add webhook security best practices
- [ ] Implement webhook signature verification
- [ ] Add monitoring for webhook failures

## Architecture

```
                                   ┌─────────────┐
                                   │             │
                                   │   Notion    │
                                   │  Database   │
                                   │             │
                                   └──────┬──────┘
                                          │
                                          │ Webhook
                                          ▼
┌─────────────┐    HTTPS    ┌──────────────────┐    Invoke    ┌─────────────┐
│   Notion    │─────────────▶│   API Gateway   │─────────────▶│   Lambda    │
│  Webhook    │             │      (TODO)      │             │  Function   │
└─────────────┘             └──────────────────┘             └─────────────┘
                                                                    │
                                                                    │
                                                              ┌─────▼─────┐
                                                              │  Recipe   │
                                                              │ Websites  │
                                                              └───────────┘
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Project Structure

```
notion_recipe_lambda/
├── lambda_function.py     # Main Lambda function
├── run_tests.sh          # Test script
├── requirements.txt      # Python dependencies
└── .env                 # Environment variables (not in repo)
``` 