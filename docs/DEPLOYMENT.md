# Intermud3 Gateway Deployment Guide

## Project Status
- **Current Phase**: Phase 3 Complete (2025-08-20) - Ready for Production
- **Phase 2 Complete**: Core services implemented
- **Phase 3 Complete**: JSON-RPC API, WebSocket/TCP servers, client libraries, full documentation
- **Test Coverage**: 78% overall with 1200+ tests
- **Performance**: 1000+ msg/sec throughput, <100ms latency achieved
- **Version**: 0.3.0

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
- Inbound TCP port 8080 (WebSocket API)
- Inbound TCP port 8081 (TCP API)
- Stable internet connection

## Installation Methods

### Quick Deploy (Recommended for Production)

```bash
# As root, create a dedicated user
useradd -m -s /bin/bash intermud3
usermod -aG docker intermud3  # If using Docker
mkdir -p /home/intermud3/{logs,data}
chown -R intermud3:intermud3 /home/intermud3/

# Switch to the intermud3 user
sudo su - intermud3

# Clone and setup
git clone https://github.com/LuminariMUD/Intermud3.git
cd Intermud3
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env  # Set your MUD_NAME and other settings

# Test run
python -m src  # Ctrl+C to stop when confirmed working
```

### Method 1: From Source

```bash
# Clone the repository
git clone https://github.com/LuminariMUD/Intermud3.git
cd Intermud3

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy configuration
cp .env.example .env
# Edit .env to set your MUD name and other settings
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
# API Configuration
API_WS_HOST=0.0.0.0
API_WS_PORT=8080
API_TCP_HOST=0.0.0.0
API_TCP_PORT=8081
I3_GATEWAY_SECRET=your-secret-key-here

# MUD Configuration
MUD_NAME=LuminariMUD
MUD_PORT=4100
MUD_ADMIN_EMAIL=max@aiwithapex.com
MUD_TYPE=Circle
MUD_STATUS=open

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
api:
  websocket:
    host: ${API_WS_HOST:0.0.0.0}
    port: ${API_WS_PORT:8080}
  tcp:
    host: ${API_TCP_HOST:0.0.0.0}
    port: ${API_TCP_PORT:8081}
  auth:
    secret: ${I3_GATEWAY_SECRET}
  
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

# Run with default config (uses .env and config/config.yaml)
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
  -p 8080:8080 \
  -p 8081:8081 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  intermud3-gateway:latest

# With environment variables
docker run -d \
  --name i3-gateway \
  -p 8080:8080 \
  -p 8081:8081 \
  -e MUD_NAME=MyMUD \
  -e MUD_PORT=4000 \
  -e LOG_LEVEL=DEBUG \
  intermud3-gateway:latest

# With env file
docker run -d \
  --name i3-gateway \
  -p 8080:8080 \
  -p 8081:8081 \
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
      - "8080:8080"  # WebSocket API
      - "8081:8081"  # TCP API
    environment:
      - MUD_NAME=${MUD_NAME}
      - MUD_PORT=${MUD_PORT}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
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

### Pre-Production Checklist

Before deploying to production:

1. **Register MUD Name with I3 Network**
   - Contact I3 router administrators to register "LuminariMUD"
   - This prevents the 5-minute disconnection cycle for unregistered MUDs
   - Primary router admin contact: Check *i3 router status page

2. **Generate Production Secrets**
   ```bash
   # Generate API key for LuminariMUD
   openssl rand -hex 32 > luminari-api-key.txt
   
   # Generate gateway secret
   openssl rand -hex 32 > gateway-secret.txt
   ```

3. **SSL/TLS Setup (Optional but Recommended)**
   - Obtain SSL certificate for WebSocket connections
   - Configure reverse proxy (nginx/Apache) for SSL termination

4. **Backup Strategy**
   - Set up automated daily backups of state/ directory
   - Configure backup retention policy (recommended: 7 days)

### Production Environment Variables

Create `/opt/i3-gateway/.env.production`:

```bash
# Production settings for LuminariMUD
MUD_NAME=LuminariMUD
MUD_PORT=4100
MUD_ADMIN_EMAIL=max@aiwithapex.com
MUD_TYPE=Circle
MUD_STATUS=open

# API Configuration
API_WS_HOST=0.0.0.0
API_WS_PORT=8080
API_TCP_HOST=0.0.0.0
API_TCP_PORT=8081
API_AUTH_ENABLED=true
API_KEY_LUMINARI=<generated-api-key>
I3_GATEWAY_SECRET=<generated-secret>

# I3 Router (Production)
I3_ROUTER_HOST=204.209.44.3
I3_ROUTER_PORT=8080

# Logging (Production)
LOG_LEVEL=WARNING
LOG_FILE=/var/log/i3-gateway/production.log

# Performance Tuning
MAX_CONNECTIONS=500
MESSAGE_QUEUE_SIZE=5000
CACHE_TTL=600
```

### Systemd Service (Recommended for Production)

A systemd service file is included in the repository. As root:

```bash
# Copy the service file
cp /home/intermud3/Intermud3/i3-gateway.service /etc/systemd/system/

# Create log directory
mkdir -p /home/intermud3/logs
chown intermud3:intermud3 /home/intermud3/logs

# Enable and start the service
systemctl daemon-reload
systemctl enable i3-gateway
systemctl start i3-gateway
systemctl status i3-gateway
```

The included service file (`i3-gateway.service`):

```ini
[Unit]
Description=Intermud3 Gateway Service
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=intermud3
Group=intermud3
WorkingDirectory=/home/intermud3/Intermud3
Environment="PATH=/home/intermud3/Intermud3/venv/bin"
ExecStart=/home/intermud3/Intermud3/venv/bin/python -m src
Restart=always
RestartSec=10
StandardOutput=append:/home/intermud3/logs/stdout.log
StandardError=append:/home/intermud3/logs/stderr.log

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
# HTTP health check
curl http://localhost:8080/health

# Expected response:
# {
#   "status": "healthy",
#   "service": "i3-gateway-api",
#   "websocket_connections": 0,
#   "active_sessions": 0
# }

# Metrics endpoint
curl http://localhost:8080/metrics

# TCP health check (if TCP API enabled)
nc -zv localhost 8081
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