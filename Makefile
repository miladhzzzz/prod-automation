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

down:
	@echo "Shutting down services..."
	@$(COMPOSE) down
	@echo "Services are down."

solo:
	@echo "Bringing up prod-auto service..."
	@chmod +x init.sh && ./init.sh
	@echo "prod-auto service is up."

sync:
	@echo "Syncing code with upstream and restarting services..."
	@$(COMPOSE) down
	@git pull
	@$(COMPOSE) build
	@$(COMPOSE) up -d
	@echo "Sync complete."

setup:
	@echo "Setting up the host OS..."
	@cd scripts && chmod +x setup-host.sh && ./setup-host.sh
	@echo "Setup complete! now use make up."

cd:
	@echo "Setting Up Kube-o-Matic continious Delivery integration..."
	@$(COMPOSE) -f cd-docker-compose.yml up -d
	@echo "Kube-o-matic Deployed successfully" 

.PHONY: build up down solo sync setup cd
