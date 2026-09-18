VERSION ?= $(shell git describe --always --tags)
DOCKER_TAG ?= latest

export DOCKER_BUILDKIT=1

.DEFAULT_GOAL := help

.env: ## Prepare .env file
	cp .env.sample .env
	sed -i 's/PGHOST=db/PGHOST=localhost/g' .env

settings.py: ## Prepare settings.py
	cp -vn default_settings.py settings.py

.venv/touchfile: settings.py .env
	python -m venv .venv
	. .venv/bin/activate; \
	pip install poetry; \
	poetry install --no-root
	touch .venv/touchfile

venv: .venv/touchfile ## Setup a python virtual environment and install the required dependencies

.PHONY: run-db-localhost
run-db-localhost: ## Run the db in a docker container and expose the container on port 5432
	docker compose -f docker-compose.yml -f docker-compose.localhost.yml up -d db

.PHONY: run-manage-scripts
run-manage-scripts: venv run-db-localhost ## Run the Django management scripts
	. .venv/bin/activate; \
	python manage.py migrate; \
	python manage.py collectstatic --no-input; \
	python manage.py compilemessages --locale=de; \
	python manage.py fixturize; \
	python manage.py seed

.PHONY: run-server
run-server: run-manage-scripts ## Run the server on the host machine
	. .venv/bin/activate; \
	python manage.py runserver

.PHONY: docker-run-server
docker-run-server: .env prepare_env ## Run the server in a dockerized environment
	docker compose exec api bash -c "python manage.py seed"

.PHONY: clean
clean: docker-clean ## Clean the environment
	rm -rf .venv || true
	rm settings.py || true
	rm .env || true
	rm -rf static/* || true

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

.PHONY: docker-test
docker-test: docker-run-server ## Run tests in docker container
	docker compose exec -T api python manage.py test -v 2 --force-color --noinput

.PHONY: test
test: run-manage-scripts ## Run tests on host machine
	. .venv/bin/activate; \
	python manage.py test -v 2 --force-color --noinput

.PHONY: prepare_env
prepare_env: docker-down ## Prepare Docker environment
	docker compose up --build -d
	until [ "$$(docker inspect -f '{{.State.Health.Status}}' geoshop-back-api-1)" = "healthy" ]; do \
		echo "Waiting for api..."; \
		sleep 1; \
	done;

.PHONY: docker-down
docker-down: ## Stop and remove docker containers
	docker compose down --remove-orphans

.PHONY: docker-clean
docker-clean: ## Stop and remove docker containers, and remove volumes and images
	docker compose down --remove-orphans -v --rmi='all'

.PHONY: help
help: ## Display this help
	@echo "Usage: make <target>"
	@echo
	@echo "Available targets:"
	@grep --extended-regexp --no-filename '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "	%-20s%s\n", $$1, $$2}'