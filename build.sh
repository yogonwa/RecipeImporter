#!/bin/bash
set -e

echo "🔨 Building Lambda package using Docker..."

# Build the Docker image
docker build --no-cache -t recipe-lambda .

# Create a container and copy the zip file
CONTAINER_ID=$(docker create recipe-lambda)
docker cp $CONTAINER_ID:/output/lambda_function.zip .

# Clean up
docker rm $CONTAINER_ID
docker image prune -f

# Verify package size
PACKAGE_SIZE=$(du -h lambda_function.zip | cut -f1)
echo "📊 Package size: $PACKAGE_SIZE"

echo "✅ Done! Deployment package created as lambda_function.zip"

# Check if package size exceeds Lambda limits
MAX_SIZE_MB=250
ACTUAL_SIZE_MB=$(du -m lambda_function.zip | cut -f1)
if [ $ACTUAL_SIZE_MB -gt $MAX_SIZE_MB ]; then
    echo "⚠️  Warning: Package size ($ACTUAL_SIZE_MB MB) exceeds Lambda limit ($MAX_SIZE_MB MB)"
else
    echo "✅ Package size is within Lambda limits"
fi
