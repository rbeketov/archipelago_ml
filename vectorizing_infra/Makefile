.PHONY: up wait run

VENV_DIR=../.venv
SCRIPT=init_qdrant/init_script.py
SERVICE=qdrant

up:
	docker-compose up -d

wait: up
	@echo "Ожидание готовности контейнера $(SERVICE)..."
	@while ! docker-compose ps | grep "$(SERVICE)" | grep "Up"; do sleep 2; done
	@echo "Контейнер $(SERVICE) готов!"

run: wait
	$(VENV_DIR)/bin/python $(SCRIPT)

