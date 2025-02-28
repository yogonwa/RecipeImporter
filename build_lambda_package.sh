#!/bin/bash

# Create and activate a temporary virtual environment
echo "Creating virtual environment..."
python3 -m venv package_env
source package_env/bin/activate

# Create a temporary directory for the package
echo "Creating temporary directory..."
mkdir -p lambda_package

# Install dependencies into the package directory
echo "Installing dependencies..."
pip install --platform manylinux2014_x86_64 --implementation cp --python-version 3.9 --only-binary=:all: --target lambda_package -r requirements.txt
pip install --platform manylinux2014_x86_64 --implementation cp --python-version 3.9 --only-binary=:all: --target lambda_package lxml

# Copy the Lambda function code
echo "Copying Lambda function code..."
cp lambda_function.py lambda_package/

# Create the deployment package
echo "Creating deployment package..."
cd lambda_package
zip -r ../lambda_deployment_package.zip .
cd ..

# Clean up
echo "Cleaning up..."
rm -rf lambda_package
rm -rf package_env

echo "Done! Deployment package created as lambda_deployment_package.zip" 