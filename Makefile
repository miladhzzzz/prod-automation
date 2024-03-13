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
	@./init.sh
	@echo "prod-auto service is up."

sync:
	@echo "Syncing code with upstream..."
	@git pull
	@echo "Sync complete."

.PHONY: build up down solo sync
