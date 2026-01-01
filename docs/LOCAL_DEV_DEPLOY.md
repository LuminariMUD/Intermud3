# Local Development Deployment Guide (WSL2 Ubuntu)

This guide documents how to deploy the I3 Gateway locally on WSL2 Ubuntu for development and testing, with ngrok tunnels for external MUD access.

## Environment Files

| File | Purpose |
|------|---------|
| `.env` | **Primary** - Loaded automatically by the gateway at startup |
| `.env.example` | Template file - copy to `.env` and customize |
| `.env.local` | Optional - for personal overrides (not auto-loaded, mentioned in comments only) |

The gateway loads `.env` by default. The `.env.local` pattern is a convention suggestion in comments but is **not** automatically loaded by the application.

## Prerequisites

Before starting, ensure you have:

- **Python 3.9+** (tested with Python 3.12.3)
- **pip** (tested with pip 24.0)
- **ngrok** with authenticated paid account (tested with ngrok 3.34.1)

Verify prerequisites:
```bash
python3 --version   # Should be 3.9+
pip3 --version
ngrok version
ngrok config check  # Should show "Valid configuration file"
```

## Quick Start

```bash
cd /home/aiwithapex/projects/Intermud3

# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Create required directories
mkdir -p logs state

# 3. Start the gateway
source venv/bin/activate
python -m src --debug &

# 4. Start ngrok tunnels (in separate terminal or background)
ngrok start --all --config ngrok.yml &

# 5. Verify
curl http://localhost:8080/health
```

## Step-by-Step Setup

### Step 1: Python Virtual Environment

```bash
cd /home/aiwithapex/projects/Intermud3
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Dependencies installed:**
- pyyaml >= 6.0
- structlog >= 23.0
- aiohttp >= 3.9.0
- pydantic >= 2.0
- python-dotenv >= 1.0.0
- click >= 8.0
- psutil >= 5.9.0

### Step 2: Environment Configuration

The `.env` file should be configured with:

```bash
# MUD Configuration
MUD_NAME=LuminariMUD
MUD_PORT=4100
MUD_ADMIN_EMAIL=admin@yourmud.com

# I3 Router Configuration
I3_ROUTER_HOST=204.209.44.3
I3_ROUTER_PORT=8080

# API Configuration
API_WS_HOST=0.0.0.0
API_WS_PORT=8080
API_TCP_HOST=0.0.0.0
API_TCP_PORT=8081

# Security (IMPORTANT: Generate unique secrets!)
I3_GATEWAY_SECRET=<your-64-char-hex-secret>
API_KEY_LUMINARI=<your-api-key>

# Logging
LOG_LEVEL=DEBUG

# Development Settings
DEBUG=true
RELOAD=true
```

**Generate a secure secret:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Step 3: Create Required Directories

```bash
mkdir -p logs state
```

- `logs/` - Application logs (10MB rolling files)
- `state/` - Persistent state data

### Step 4: ngrok Configuration

The ngrok settings are defined in `.env`:
```bash
NGROK_DOMAIN=i3.ngrok.dev
NGROK_INSPECTOR_PORT=4042
NGROK_AUTHTOKEN=<your-authtoken>
NGROK_API_KEY=<your-api-key>
```

Create `ngrok.yml` in the project root (uses values from `.env`):

```yaml
version: "3"
agent:
    authtoken: <your-ngrok-authtoken>
    web_addr: 127.0.0.1:4042  # NGROK_INSPECTOR_PORT from .env

tunnels:
    i3-websocket:
        proto: http
        addr: 8080
        domain: i3.ngrok.dev  # NGROK_DOMAIN from .env (paid feature)
        inspect: true

    i3-tcp:
        proto: tcp
        addr: 8081
```

**Note:** Custom domains require a paid ngrok account. The `web_addr` port (4042) avoids conflicts with other ngrok instances.

### Step 5: Start the I3 Gateway

```bash
source venv/bin/activate
python -m src --debug
```

**Successful startup shows:**
```json
{"event": "I3 Gateway started successfully"}
{"event": "Connection state changed", "state": "connected"}
{"event": "API server started", "host": "0.0.0.0", "port": 8080}
{"event": "TCP server listening on 0.0.0.0:8081"}
```

### Step 6: Start ngrok Tunnels

```bash
ngrok start --all --config ngrok.yml
```

Check tunnel URLs:
```bash
curl -s http://localhost:4041/api/tunnels | python3 -m json.tool
```

**Example output:**
- WebSocket: `https://xxxxx.ngrok-free.dev` -> localhost:8080
- TCP: `tcp://x.tcp.eu.ngrok.io:xxxxx` -> localhost:8081

### Step 7: Verification

**Health Check (local):**
```bash
curl http://localhost:8080/health
```

**Expected response:**
```json
{
    "status": "healthy",
    "service": "i3-gateway-api",
    "websocket_connections": 0,
    "active_sessions": 0
}
```

**Health Check (via ngrok):**
```bash
curl https://<your-ngrok-url>/health
```

## Port Summary

| Port | Protocol | Purpose | External Access |
|------|----------|---------|-----------------|
| 8080 | HTTP/WS | WebSocket API, health checks | https://i3.ngrok.dev |
| 8081 | TCP | Raw TCP socket API | tcp://x.tcp.eu.ngrok.io:xxxxx |
| 4042 | HTTP | ngrok web interface | localhost only |

## Running as Background Services

### Start Gateway in Background
```bash
source venv/bin/activate
nohup python -m src --debug > logs/gateway.log 2>&1 &
echo $! > .gateway.pid
```

### Start ngrok in Background
```bash
nohup ngrok start --all --config ngrok.yml > logs/ngrok.log 2>&1 &
echo $! > .ngrok.pid
```

### Stop Services
```bash
kill $(cat .gateway.pid) 2>/dev/null
kill $(cat .ngrok.pid) 2>/dev/null
```

## Troubleshooting

### ngrok "port already in use"
If port 4040 is in use by another ngrok instance:
```yaml
# In ngrok.yml, add under agent:
agent:
    web_addr: 127.0.0.1:4041
```

### Gateway won't connect to I3 router
1. Check firewall allows outbound TCP to 204.209.44.3:8080
2. Verify `.env` has correct router settings
3. Check logs: `tail -f logs/i3-gateway.log`

### "Module not found" errors
Ensure you've activated the virtual environment:
```bash
source venv/bin/activate
```

### ngrok tunnels not showing
1. Check ngrok config syntax: `ngrok config check`
2. View ngrok logs: `cat logs/ngrok.log`
3. Ensure authtoken is valid

## External MUD Connection

External MUDs can connect using the ngrok URLs:

**WebSocket Connection (recommended for web clients):**
```
wss://i3.ngrok.dev/ws
```

**TCP Connection (for traditional MUD clients):**
```
tcp://x.tcp.eu.ngrok.io:<port>
```
*(TCP port changes on each ngrok restart - check `curl http://localhost:4042/api/tunnels`)*

Use the API key configured in `.env` for authentication.

## Files Reference

| File | Purpose |
|------|---------|
| `.env` | Environment variables |
| `config/config.yaml` | Main configuration |
| `ngrok.yml` | ngrok tunnel configuration |
| `logs/` | Application logs |
| `state/` | Persistent state |
| `venv/` | Python virtual environment |

## Next Steps

- Test WebSocket connection with a client
- Configure your MUD to use the gateway API
- Monitor logs: `tail -f logs/i3-gateway.log`
- Access ngrok web interface: `http://localhost:4041`
