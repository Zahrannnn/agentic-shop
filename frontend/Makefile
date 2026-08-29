# CORELIA Next Boilerplate - Docker usage.
# Edit infra/.env, then `make up` to apply env changes without rebuilding.

COMPOSE := docker compose -f infra/docker-compose.yml --project-directory infra

-include infra/.env
export

.PHONY: help env build up rebuild down restart logs ps shell push clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-12s %s\n", $$1, $$2}'

env: ## Copy infra/.env.example to infra/.env if missing
	@if [ ! -f infra/.env ]; then cp infra/.env.example infra/.env && echo "Created infra/.env"; else echo "infra/.env already exists"; fi

build: ## Build the Docker image
	$(COMPOSE) build

up: ## Start app from current image (regenerates runtime env, no rebuild)
	$(COMPOSE) up -d

rebuild: build up ## Rebuild image and start

down: ## Stop and remove containers
	$(COMPOSE) down

restart: ## Restart app (regenerates runtime env)
	$(COMPOSE) restart

logs: ## Tail logs
	$(COMPOSE) logs -f

ps: ## Show container status
	$(COMPOSE) ps

shell: ## Open a shell in the app container
	$(COMPOSE) exec app sh

push: ## Push image to registry
	docker push "${HUB_URL}/${APP_NAME}:${APP_VERSION}"

clean: down ## Stop containers and remove the local image (keeps .env)
	@docker image rm "${HUB_URL}/${APP_NAME}:${APP_VERSION}" 2>/dev/null || true
