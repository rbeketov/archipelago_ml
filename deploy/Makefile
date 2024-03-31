PROJECT_DIR ?= /home/ubuntu/archipelago_ml

start:
	sudo systemctl start tg_bot

stop:
	sudo systemctl stop tg_bot

restart:
	sudo systemctl stop tg_bot
	sudo systemctl start tg_bot

demonize:
	PROJECT_DIR=${PROJECT_DIR} /bin/sh daemon.sh

logs:
	journalctl -u ml.service

