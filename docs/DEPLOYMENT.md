# Intermud3 Gateway Deployment Guide

## Project Status
- **Current Phase**: Phase 3 - Gateway API Protocol
- **Phase 2 Complete**: Core services implemented with 60% test coverage
- **Version**: 0.2.0

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
- [Configuration](#configuration)
- [Running the Gateway](#running-the-gateway)
- [Docker Deployment](#docker-deployment)
- [Production Deployment](#production-deployment)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements
- Python 3.9 or higher
- 512MB RAM minimum (1GB recommended)
- 100MB disk space
- Network connectivity to I3 routers

### Network Requirements
- Outbound TCP port 8080 (to I3 routers)
- Inbound TCP port 4001 (from your MUD server)
- Stable internet connection

## Installation Methods

### Method 1: From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/intermud3-gateway.git
cd intermud3-gateway

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy configuration
cp config/config.yaml.example config/config.yaml
cp .env.example .env
```

### Method 2: Using pip (Future)

```bash
pip install intermud3-gateway
```

### Method 3: Docker

```bash
docker pull intermud3/gateway:latest
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Gateway Configuration
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=4001
GATEWAY_SECRET=your-secret-key-here

# MUD Configuration
MUD_NAME=YourMUD
MUD_PORT=4000
MUD_ADMIN_EMAIL=admin@yourmud.com
MUD_TYPE=Circle
MUD_STATUS=Development

# I3 Router Configuration
I3_ROUTER_HOST=204.209.44.3
I3_ROUTER_PORT=8080
I3_ROUTER_NAME=*i3

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/i3-gateway.log

# Performance
MAX_CONNECTIONS=100
MESSAGE_QUEUE_SIZE=1000
CACHE_TTL=300

# Security
RATE_LIMIT_ENABLED=true
RATE_LIMIT_TELLS=10
RATE_LIMIT_CHANNELS=20
```

### YAML Configuration

Edit `config/config.yaml`:

```yaml
gateway:
  host: ${GATEWAY_HOST:0.0.0.0}
  port: ${GATEWAY_PORT:4001}
  secret: ${GATEWAY_SECRET}
  
mud:
  name: ${MUD_NAME}
  port: ${MUD_PORT:4000}
  admin_email: ${MUD_ADMIN_EMAIL}
  type: ${MUD_TYPE:LP}
  status: ${MUD_STATUS:Development}
  
router:
  primary:
    name: ${I3_ROUTER_NAME:*i3}
    host: ${I3_ROUTER_HOST:204.209.44.3}
    port: ${I3_ROUTER_PORT:8080}
  fallback:
    - name: "*dalet"
      host: "97.107.133.86"
      port: 8787
    - name: "*wpr"
      host: "195.242.99.94"
      port: 8080
      
services:
  tell:
    enabled: true
    queue_size: 100
  channel:
    enabled: true
    default_channels:
      - chat
      - code
  who:
    enabled: true
    cache_ttl: 60
  finger:
    enabled: true
  locate:
    enabled: true
  emoteto:
    enabled: true
    
logging:
  level: ${LOG_LEVEL:INFO}
  file: ${LOG_FILE}
  format: json
  rotate_size: 10485760  # 10MB
  backup_count: 5
  
performance:
  max_connections: ${MAX_CONNECTIONS:100}
  message_queue_size: ${MESSAGE_QUEUE_SIZE:1000}
  cache_ttl: ${CACHE_TTL:300}
  connection_timeout: 30
  reconnect_delay: 5
  
security:
  rate_limiting:
    enabled: ${RATE_LIMIT_ENABLED:true}
    tells_per_minute: ${RATE_LIMIT_TELLS:10}
    channels_per_minute: ${RATE_LIMIT_CHANNELS:20}
    who_per_minute: 5
  ip_whitelist: []
  ip_blacklist: []
```

## Running the Gateway

### Development Mode

```bash
# Activate virtual environment
source venv/bin/activate

# Run with default config
python -m src

# Run with specific config
python -m src -c config/config.yaml

# Run with debug logging
LOG_LEVEL=DEBUG python -m src

# Run with environment file
python -m src --env-file production.env
```

### Production Mode

```bash
# Using gunicorn (for WSGI compatibility)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker src.gateway:app

# Using supervisor
supervisorctl start i3-gateway

# Using systemd
systemctl start i3-gateway
```

## Docker Deployment

### Building the Image

```bash
# Build from Dockerfile
docker build -t intermud3-gateway:latest .

# Build with custom tag
docker build -t myregistry/i3-gateway:v1.0.0 .
```

### Running with Docker

```bash
# Basic run
docker run -d \
  --name i3-gateway \
  -p 4001:4001 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  intermud3-gateway:latest

# With environment variables
docker run -d \
  --name i3-gateway \
  -p 4001:4001 \
  -e MUD_NAME=MyMUD \
  -e MUD_PORT=4000 \
  -e LOG_LEVEL=DEBUG \
  intermud3-gateway:latest

# With env file
docker run -d \
  --name i3-gateway \
  -p 4001:4001 \
  --env-file .env \
  intermud3-gateway:latest
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  gateway:
    image: intermud3-gateway:latest
    container_name: i3-gateway
    restart: unless-stopped
    ports:
      - "4001:4001"
    environment:
      - MUD_NAME=${MUD_NAME}
      - MUD_PORT=${MUD_PORT}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "python", "-c", "import socket; s=socket.socket(); s.connect(('localhost', 4001)); s.close()"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - mud-network

networks:
  mud-network:
    driver: bridge
```

Run with docker-compose:

```bash
docker-compose up -d
docker-compose logs -f gateway
docker-compose down
```

## Production Deployment

### Systemd Service

Create `/etc/systemd/system/i3-gateway.service`:

```ini
[Unit]
Description=Intermud3 Gateway Service
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=i3gateway
Group=i3gateway
WorkingDirectory=/opt/i3-gateway
Environment="PATH=/opt/i3-gateway/venv/bin"
ExecStart=/opt/i3-gateway/venv/bin/python -m src
Restart=always
RestartSec=10
StandardOutput=append:/var/log/i3-gateway/stdout.log
StandardError=append:/var/log/i3-gateway/stderr.log

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/i3-gateway/data /var/log/i3-gateway

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable i3-gateway
sudo systemctl start i3-gateway
sudo systemctl status i3-gateway
```

### Supervisor Configuration

Create `/etc/supervisor/conf.d/i3-gateway.conf`:

```ini
[program:i3-gateway]
command=/opt/i3-gateway/venv/bin/python -m src
directory=/opt/i3-gateway
user=i3gateway
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=10
redirect_stderr=true
stdout_logfile=/var/log/supervisor/i3-gateway.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=5
environment=PATH="/opt/i3-gateway/venv/bin",MUD_NAME="YourMUD"
```

### Kubernetes Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: i3-gateway
  labels:
    app: i3-gateway
spec:
  replicas: 1
  selector:
    matchLabels:
      app: i3-gateway
  template:
    metadata:
      labels:
        app: i3-gateway
    spec:
      containers:
      - name: gateway
        image: intermud3-gateway:latest
        ports:
        - containerPort: 4001
        env:
        - name: MUD_NAME
          valueFrom:
            configMapKeyRef:
              name: i3-config
              key: mud_name
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          tcpSocket:
            port: 4001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          tcpSocket:
            port: 4001
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: i3-gateway
spec:
  selector:
    app: i3-gateway
  ports:
  - port: 4001
    targetPort: 4001
  type: ClusterIP
```

## Monitoring

### Health Check Endpoints

```bash
# TCP health check
nc -zv localhost 4001

# HTTP health check (if enabled)
curl http://localhost:8080/health

# Metrics endpoint
curl http://localhost:8080/metrics
```

### Logging

Log locations:
- Development: `./logs/i3-gateway.log`
- Docker: `/app/logs/i3-gateway.log`
- Production: `/var/log/i3-gateway/i3-gateway.log`

Log rotation configuration:

```bash
# /etc/logrotate.d/i3-gateway
/var/log/i3-gateway/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 i3gateway i3gateway
    postrotate
        systemctl reload i3-gateway
    endscript
}
```

### Prometheus Metrics

Example Prometheus configuration:

```yaml
scrape_configs:
  - job_name: 'i3-gateway'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
```

## Troubleshooting

### Common Issues

#### Connection Refused
```bash
# Check if service is running
systemctl status i3-gateway
ps aux | grep i3-gateway

# Check port binding
netstat -tlnp | grep 4001
ss -tlnp | grep 4001

# Check firewall
iptables -L -n | grep 4001
ufw status
```

#### Cannot Connect to I3 Router
```bash
# Test router connectivity
telnet 204.209.44.3 8080
nc -zv 204.209.44.3 8080

# Check DNS resolution
nslookup your-mud.com

# Verify configuration
python -m src --validate-config
```

#### High Memory Usage
```bash
# Check memory usage
ps aux | grep i3-gateway
top -p $(pgrep -f i3-gateway)

# Adjust cache settings
CACHE_TTL=60 python -m src

# Enable memory profiling
LOG_LEVEL=DEBUG python -m src --profile-memory
```

### Debug Mode

Enable debug logging:

```bash
# Environment variable
LOG_LEVEL=DEBUG python -m src

# Command line
python -m src --log-level DEBUG

# Configuration file
# Set logging.level: DEBUG in config.yaml
```

### Test Connection

Test script to verify gateway connection:

```python
#!/usr/bin/env python3
import socket
import json

def test_gateway():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('localhost', 4001))
    
    # Send ping
    request = {
        "jsonrpc": "2.0",
        "method": "ping",
        "id": 1
    }
    s.send(json.dumps(request).encode() + b'\n')
    
    # Receive response
    response = s.recv(1024).decode()
    print(f"Response: {response}")
    
    s.close()

if __name__ == "__main__":
    test_gateway()
```

## Backup and Recovery

### Backup State

```bash
# Backup data directory
tar -czf i3-gateway-backup-$(date +%Y%m%d).tar.gz data/

# Backup with timestamp
rsync -av --delete data/ backups/data-$(date +%Y%m%d)/
```

### Restore State

```bash
# Stop service
systemctl stop i3-gateway

# Restore data
tar -xzf i3-gateway-backup-20240119.tar.gz

# Start service
systemctl start i3-gateway
```

## Security Considerations

### Firewall Rules

```bash
# Allow gateway port
ufw allow 4001/tcp comment 'I3 Gateway API'

# Restrict to specific IP
ufw allow from 192.168.1.100 to any port 4001

# IPTables example
iptables -A INPUT -p tcp --dport 4001 -s 192.168.1.0/24 -j ACCEPT
```

### SSL/TLS Configuration

For production, consider using a reverse proxy with SSL:

```nginx
# nginx configuration
server {
    listen 443 ssl;
    server_name i3gateway.yourmud.com;
    
    ssl_certificate /etc/ssl/certs/yourmud.crt;
    ssl_certificate_key /etc/ssl/private/yourmud.key;
    
    location / {
        proxy_pass http://localhost:4001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Performance Tuning

### System Tuning

```bash
# Increase file descriptors
ulimit -n 65536

# TCP tuning
sysctl -w net.core.somaxconn=1024
sysctl -w net.ipv4.tcp_tw_reuse=1
```

### Application Tuning

```yaml
# config.yaml
performance:
  worker_threads: 4
  async_workers: 10
  connection_pool_size: 20
  message_batch_size: 50
  cache_size: 10000
```