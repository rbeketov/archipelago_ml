.PHONY: up wait init

VENV_DIR=../.venv
SCRIPT=init_qdrant/init_script.py
SERVICE=qdrant

up:
	sudo docker-compose up -d

init:
	$(VENV_DIR)/bin/python $(SCRIPT)

