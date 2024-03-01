FROM ubuntu:latest

# Install dependencies
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common

# Install Docker CLI client
RUN apt-get update && apt-get install -y docker

# Set up working directory and copy your application code
WORKDIR /app
COPY . .

# Your CMD or ENTRYPOINT command goes here

RUN pip install requirements.txt

CMD ["python3", "main.py"]
