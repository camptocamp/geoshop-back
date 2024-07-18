VERSION ?= $(shell git describe --always --tags)
DOCKER_TAG ?= latest

export DOCKER_BUILDKIT=1

.PHONY: build
build: ## Build docker image
	docker build --tag=camptocamp/geoshop-api:$(VERSION) \
		--build-arg=VERSION=$(VERSION) .
	docker tag camptocamp/geoshop-api:$(VERSION) camptocamp/geoshop-api:$(DOCKER_TAG)

.PHONY: test
test: ## Run tests
	docker compose exec -T api python manage.py test -v 2 --force-color --noinput

.PHONY: prepare_env
prepare_env: destroy_env build ## Prepare Docker environment
	docker compose up -d
	until [ "$$(docker inspect -f '{{.State.Health.Status}}' geoshop-back-api-1)" = "healthy" ]; do \
		echo "Waiting for api..."; \
		sleep 1; \
	done;

.PHONY: destroy_env
destroy_env: ## Destroy Docker environment
	docker compose down --remove-orphans

.PHONY: help
help: ## Display this help
	@echo "Usage: make <target>"
	@echo
	@echo "Available targets:"
	@grep --extended-regexp --no-filename '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "	%-20s%s\n", $$1, $$2}'