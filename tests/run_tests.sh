#!/bin/bash

# Test Runner Script for Recipe Importer
# ------------------------------------
#
# This script runs all tests for the Recipe Importer project.
# It includes unit tests, integration tests, and generates coverage reports.
#
# Features:
# - Runs pytest with coverage reporting
# - Validates environment variables
# - Provides detailed test output
# - Generates HTML coverage report

# Exit on error
set -e

# Check for required environment variables
if [ -z "$NOTION_API_KEY" ] || [ -z "$NOTION_DATABASE_ID" ]; then
    echo "❌ Error: Missing required environment variables"
    echo "Please set:"
    echo "  - NOTION_API_KEY"
    echo "  - NOTION_DATABASE_ID"
    exit 1
fi

echo "🧪 Running tests..."

# Create and activate virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install pytest pytest-cov
else
    source venv/bin/activate
fi

# Run tests with coverage
pytest --cov=lambda_function \
      --cov-report=term-missing \
      --cov-report=html \
      -v \
      tests/

# Check test exit code
if [ $? -eq 0 ]; then
    echo "✅ All tests passed!"
    echo "📊 Coverage report generated in htmlcov/index.html"
else
    echo "❌ Some tests failed"
    exit 1
fi 