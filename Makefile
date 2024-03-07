# up: bring everything up
up:
	docker-compose up -d

# down: shut everything down
down: 
	docker-compose down

# solo: will bring up only the prod-auto machine
solo:
	./init.sh

# sync: syncs the code with upstream using git pull
sync:
	git pull