FROM amazonlinux:2

# Install dependencies
RUN yum update -y && \
    yum install -y python3 python3-pip python3-devel gcc libxml2-devel libxslt-devel zip git

# Set working directory
WORKDIR /var/task

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install -r requirements.txt -t python/

# Create ZIP file
RUN cd python && zip -r9 /var/task/lambda_package.zip . && \
    cd /var/task && zip -g lambda_package.zip lambda_function.py
