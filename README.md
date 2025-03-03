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

## Project Structure

```
notion_recipe_lambda/
├── lambda_function.py     # Main Lambda function
├── Dockerfile            # Docker build configuration
├── build.sh             # Build script
├── requirements.txt     # Python dependencies
├── tests/              # Test suite
│   ├── README.md                # Test documentation
│   ├── test_recipe_importer.py  # Unit tests
│   ├── test_lambda.py          # Integration tests
│   ├── test-event.json        # Test data
│   ├── notion_webhook_example # Example data
│   └── run_tests.sh          # Test runner
└── .env                # Environment variables (not in repo)
```

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/notion_recipe_lambda.git
cd notion_recipe_lambda
```

2. Set up environment variables in `.env`:
```bash
NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_database_id
```

3. Build the Lambda package:
```bash
chmod +x build.sh
./build.sh
```

## Testing

The project includes a comprehensive test suite. See [tests/README.md](tests/README.md) for detailed testing instructions.

Quick start:
```bash
# Run all tests with coverage
./tests/run_tests.sh

# Run specific test file
pytest tests/test_recipe_importer.py
```

## Deployment

1. Build the Lambda package:
```bash
./build.sh
```

2. Create a new Lambda function in AWS:
   - Runtime: Python 3.9
   - Architecture: x86_64
   - Memory: 256 MB (recommended)
   - Timeout: 30 seconds (recommended)

3. Upload the deployment package:
   - Upload `lambda_function.zip` to your Lambda function

4. Configure environment variables in Lambda:
   - Add `NOTION_API_KEY` and `NOTION_DATABASE_ID`

5. Set up API Gateway:
   - Create a new HTTP API
   - Configure Lambda integration
   - Set up security (API key, IAM, etc.)
   - Enable CORS if needed
   - Deploy the API

6. Configure Notion Webhook:
   - Set up webhook in your Notion integration
   - Configure webhook to trigger on page updates
   - Point webhook to your API Gateway endpoint

## Development

### Building
The project uses Docker to ensure consistent builds for AWS Lambda:
```bash
./build.sh  # Creates lambda_function.zip
```

### Testing
Run the test suite:
```bash
./tests/run_tests.sh
```

### Adding New Features
1. Update `lambda_function.py`
2. Add tests in `tests/`
3. Update documentation
4. Build and test locally
5. Deploy to AWS Lambda

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

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

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Project Structure

```
notion_recipe_lambda/
├── lambda_function.py     # Main Lambda function
├── Dockerfile            # Docker build configuration
├── build.sh             # Build script
├── requirements.txt     # Python dependencies
├── tests/              # Test suite
│   ├── README.md                # Test documentation
│   ├── test_recipe_importer.py  # Unit tests
│   ├── test_lambda.py          # Integration tests
│   ├── test-event.json        # Test data
│   ├── notion_webhook_example # Example data
│   └── run_tests.sh          # Test runner
└── .env                # Environment variables (not in repo)
``` 