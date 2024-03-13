FROM ubuntu:latest

# Install dependencies
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common

# Install Docker CLI client, git, Python3, and pip3
RUN apt-get update && apt-get install -y docker.io python3 python3-pip git

RUN curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
RUN chmod +x /usr/local/bin/docker-compose

WORKDIR /app

COPY ./app .

EXPOSE 1111

RUN pip3 install -r requirements.txt

CMD ["python3", "main.py"]
