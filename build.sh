docker build --no-cache -t lambda-build . && docker cp $(docker create lambda-build):/output/lambda_function.zip . && docker image prune -f
