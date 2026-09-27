.PHONY: help build up down restart logs migrate makemigrations test seed shell clean

help:
	@echo "Future Tech Cyber Range - Commands"
	@echo "  make build          Build docker containers"
	@echo "  make up             Start containers in background"
	@echo "  make down           Stop containers"
	@echo "  make restart        Restart containers"
	@echo "  make logs           Follow container logs"
	@echo "  make migrate        Run database migrations"
	@echo "  make makemigrations Create database migrations"
	@echo "  make test           Run test suite"
	@echo "  make seed           Seed 14-module Diploma curriculum"
	@echo "  make shell          Open Django shell inside web container"
	@echo "  make clean          Clean python cache and temporary files"

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

test:
	docker compose exec web python manage.py test

seed:
	docker compose exec web python manage.py seed_curriculum

shell:
	docker compose exec web python manage.py shell

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

