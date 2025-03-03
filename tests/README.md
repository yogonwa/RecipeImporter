# Recipe Importer Tests

This directory contains all test-related files for the Recipe Importer project.

## Directory Structure

```
tests/
├── test_recipe_importer.py  # Unit tests for recipe parsing and Notion integration
├── test_lambda.py          # Integration tests for Lambda handler
├── test-event.json        # Sample test events
├── notion_webhook_example # Example Notion webhook payloads
└── run_tests.sh          # Test runner script
```

## Running Tests

1. Set up environment variables:
   ```bash
   export NOTION_API_KEY=your_api_key
   export NOTION_DATABASE_ID=your_database_id
   ```

2. Run all tests:
   ```bash
   ./tests/run_tests.sh
   ```

3. Run specific test file:
   ```bash
   pytest tests/test_recipe_importer.py
   ```

4. Run with coverage:
   ```bash
   pytest --cov=lambda_function tests/
   ```

## Test Categories

### Unit Tests (`test_recipe_importer.py`)
- Recipe parsing functionality
- Notion block creation
- URL validation
- Error handling

### Integration Tests (`test_lambda.py`)
- Lambda handler functionality
- Event processing
- End-to-end recipe import flow

## Test Data

- `test-event.json`: Sample Lambda event payloads
- `notion_webhook_example`: Example Notion webhook data

## Adding New Tests

1. Add test cases to existing files or create new test files
2. Follow existing naming conventions
3. Include docstrings and comments
4. Update this README if adding new test categories 