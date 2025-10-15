VERSION ?= $(shell git describe --always --tags)
DOCKER_TAG ?= latest

export DOCKER_BUILDKIT=1

.DEFAULT_GOAL := help

.PHONY: build
build: ## Build docker image
	docker build --no-cache --tag=camptocamp/geoshop-api:$(VERSION) \
		--build-arg=VERSION=$(VERSION) .
	docker tag camptocamp/geoshop-api:$(VERSION) camptocamp/geoshop-api:$(DOCKER_TAG)

.PHONY: build_ghcr
build_ghcr: ## Build docker image tagged for GHCR
	docker build --tag=ghcr.io/camptocamp/geoshop-api:$(VERSION) \
		--build-arg=VERSION=$(VERSION) .
	docker tag ghcr.io/camptocamp/geoshop-api:$(VERSION) ghcr.io/camptocamp/geoshop-api:$(DOCKER_TAG)

.PHONY: push_ghcr
push_ghcr: ## Push docker image to GHCR
	docker push ghcr.io/camptocamp/geoshop-api:$(VERSION)
	docker push ghcr.io/camptocamp/geoshop-api:$(DOCKER_TAG)

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