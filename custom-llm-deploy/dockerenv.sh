#!/bin/bash
sudo apt-get update -y
sudo apt install nginx -y

sudo systemctl start nginx
sudo systemctl enable nginx

export GPU_COUNT=$(nvidia-smi -L | wc -l)

chmod +x nginx.sh

./nginx.sh 

sudo cp nginx.conf /etc/nginx/conf.d/gemma.conf

sudo nginx -t 

sudo systemctl reload nginx

curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
  | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null \
  && echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" \
  | sudo tee /etc/apt/sources.list.d/ngrok.list \
  && sudo apt update \
  && sudo apt install ngrok -y

  ngrok config add-authtoken 3EgBWIpiUNGgCEMRIRK72itNHeZ_QehS6GU3W9hEQZN2yxCC

docker compose -f docker-compose-dyn.yml up -d

ngrok http 8080