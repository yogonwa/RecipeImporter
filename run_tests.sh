#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    # Load env vars but ignore comments and empty lines
    export $(grep -v '^#' .env | xargs)
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the tests
python test_recipe_importer.py 