#!/bin/bash

# should be executed in py venv
# should be executed in with sudo

PROJECT_DIR="${PROJECT_DIR:-/home/ubuntu/archipelago_ml}"

pip install j2cli

export python_interpreter=$(which python)
export project_dir=$PROJECT_DIR
j2 ./deploy/ml.service.j2 --import-env -o /etc/systemd/system/ml.service

sudo systemctl daemon-reload
sudo systemctl enable ml.service
