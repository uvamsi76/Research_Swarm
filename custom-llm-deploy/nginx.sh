#!/bin/bash

# Default to 1 GPU if the variable is not set
GPU_COUNT=${GPU_COUNT:-1}
NGINX_CONF="nginx.conf"

# 1. Start the upstream block
echo "upstream gemma_cluster {" > $NGINX_CONF

# 2. Loop to generate the server lines
for ((i=0; i<GPU_COUNT; i++)); do
    PORT=$((8000 + i))
    echo "    server 0.0.0.0:$PORT;" >> $NGINX_CONF
done

# 3. Close the upstream block and append the server block
cat << 'EOF' >> $NGINX_CONF
}

server {
    listen 8080;
    
    location / {
        proxy_pass http://gemma_cluster;
        proxy_set_header Host $host;
        # Increase timeouts since LLM inference can take time
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
    }
}
EOF

echo "Generated Nginx config for $GPU_COUNT GPUs."