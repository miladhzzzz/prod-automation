# Variables
COMPOSE=docker-compose

# Targets
build:
	@echo "Building Docker images..."
	@$(COMPOSE) build
	@echo "Build complete."

up:
	@echo "Bringing up services..."
	@$(COMPOSE) up -d
	@echo "Services are up and running."

keygen:
	@echo "Generating AES 128-CBC Keys if they dont exist..."
	@python3 keygen.py
	@echo "Encryption Keys generated."

down:
	@echo "Shutting down services..."
	@$(COMPOSE) down
	@echo "Services are down."

sync:
	@echo "Syncing code with upstream and restarting services..."
	@git pull
	@echo "Sync complete."

setup:
	@echo "Setting up the host OS..."
	@cd scripts && chmod +x setup-host.sh && ./setup-host.sh
	@echo "Setup complete! now use make up."

cd:
	@echo "Setting Up Kube-o-Matic continious Delivery integration..."
	@$(COMPOSE) -f cd-docker-compose.yml up -d
	@echo "Kube-o-matic Deployed successfully" 

.PHONY: build up down sync setup cd keygen
