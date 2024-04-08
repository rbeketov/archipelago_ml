#!/bin/bash

# should be executed in py venv
# should be executed in with sudo

PROJECT_DIR="${PROJECT_DIR:-/home/ubuntu/archipelago_ml}"
echo $PROJECT_DIR

pip install j2cli

export python_interpreter=$(which python)
export project_dir=$PROJECT_DIR
j2 ./ml.service.j2 -e python_interpreter -e project_dir -o ml.service

sudo cp ml.service /etc/systemd/system/ml.service

sudo systemctl daemon-reload
sudo systemctl enable ml.service
