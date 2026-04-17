.PHONY: help up down smoke clean gates

help:
	@echo "Available commands:"
	@echo "  make up      - Start all services with preflight checks"
	@echo "  make down    - Stop docker compose services"
	@echo "  make smoke   - Run end-to-end smoke test"
	@echo "  make gates   - Run promotion gates locally"
	@echo "  make clean   - Stop services, remove volumes, delete minikube"

up:
	bash ./start.sh

down:
	docker compose down

smoke:
	python test_smoke.py

gates:
	python backend/promotion/gates.py --api-base-url http://localhost:8000

clean:
	docker compose down -v
	-minikube delete
