# Use AWS Lambda Python 3.9 base image
FROM public.ecr.aws/lambda/python:3.9

# Install system dependencies
RUN yum -y update && \
    yum -y install \
    gcc \
    libxml2-devel \
    libxslt-devel \
    zip \
    && yum clean all

# Create function directory and set it as working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir "Cython<3.0" && \
    # Install and compile lxml first
    pip3 install --no-cache-dir lxml==4.9.3 && \
    # Then install remaining packages
    pip3 install --target . -r requirements.txt

# Copy function code
COPY lambda_function.py .

# Create zip file including all installed packages and function code
RUN zip -r9 lambda_function.zip . && \
    mkdir -p /output && \
    cp lambda_function.zip /output/

CMD ["lambda_function.lambda_handler"] 