FROM ubuntu:latest

# Install dependencies
RUN apt-get update && apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common

# Install Docker CLI client git python3 pip3
RUN apt-get update && apt-get install -y docker.io
RUN apt-get install -y python3 python3-pip git

WORKDIR /app
COPY . .

EXPOSE 1111

RUN pip3 install -r requirements.txt

CMD ["python3", "main.py"]
