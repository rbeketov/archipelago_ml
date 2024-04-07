PROJECT_DIR ?= /home/ubuntu/archipelago_ml

start:
	sudo systemctl start ml.service

stop:
	sudo systemctl stop ml.service

restart:
	sudo systemctl stop ml.service
	sudo systemctl start ml.service

demonize:
	PROJECT_DIR=${PROJECT_DIR} /bin/sh daemon.sh

logs:
	journalctl -u ml.service

