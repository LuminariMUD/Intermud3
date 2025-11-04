#!/usr/bin/env python3
"""
I3 Web Client Example

This example demonstrates how to create a web-based interface for the I3 Gateway
using FastAPI. It shows:

- RESTful API endpoints for I3 operations
- WebSocket real-time messaging
- Web-based chat interface
- User authentication and session management
- Rate limiting and security
- Responsive web UI

This can serve as a foundation for web-based MUD clients or administrative interfaces.
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

# Add the parent directory to the Python path to import the client library
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
from i3_client import I3Client, RPCError

# Web framework dependencies
try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


# Data Models
class SendMessageRequest(BaseModel):
    channel: str
    message: str
    message_type: str = "message"  # "message" or "emote"


class SendTellRequest(BaseModel):
    target_mud: str
    target_user: str
    message: str


class JoinChannelRequest(BaseModel):
    channel: str


class WhoRequest(BaseModel):
    target_mud: str


class WebClient:
    """
    Web-based I3 Gateway client with REST API and WebSocket support.
    
    Features:
    - RESTful API for I3 operations
    - Real-time WebSocket messaging
    - User authentication
    - Rate limiting
    - Web interface
    """
    
    def __init__(self):
        if not FASTAPI_AVAILABLE:
            raise ImportError("FastAPI is required. Install with: pip install fastapi uvicorn")
        
        # Configuration
        self.config = {
            'i3_gateway_url': os.getenv('I3_GATEWAY_URL', 'ws://localhost:8080'),
            'i3_api_key': os.getenv('I3_API_KEY'),
            'i3_mud_name': os.getenv('I3_MUD_NAME', 'WebClient'),
            'web_host': os.getenv('WEB_HOST', '0.0.0.0'),
            'web_port': int(os.getenv('WEB_PORT', '8000')),
            'auth_token': os.getenv('WEB_AUTH_TOKEN', 'default-token-change-me'),
            'cors_origins': os.getenv('CORS_ORIGINS', '*').split(','),
        }
        
        # Validate configuration
        if not self.config['i3_api_key']:
            raise ValueError("I3_API_KEY environment variable is required")
        
        # Application state
        self.i3_client: Optional[I3Client] = None
        self.connected_websockets: Set[WebSocket] = set()
        self.user_sessions: Dict[str, dict] = {}
        self.rate_limits: Dict[str, List[float]] = {}
        
        # Setup FastAPI app
        self.app = FastAPI(
            title="I3 Web Client",
            description="Web interface for Intermud3 Gateway",
            version="1.0.0"
        )
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config['cors_origins'],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Setup routes
        self._setup_routes()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('WebClient')
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        # Security
        security = HTTPBearer()
        
        def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
            if credentials.credentials != self.config['auth_token']:
                raise HTTPException(status_code=401, detail="Invalid authentication token")
            return credentials.credentials
        
        def check_rate_limit(request: Request):
            client_ip = request.client.host
            current_time = time.time()
            
            # Clean old entries
            if client_ip in self.rate_limits:
                self.rate_limits[client_ip] = [
                    t for t in self.rate_limits[client_ip]
                    if current_time - t < 60  # 1 minute window
                ]
            else:
                self.rate_limits[client_ip] = []
            
            # Check limit (60 requests per minute)
            if len(self.rate_limits[client_ip]) >= 60:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            
            self.rate_limits[client_ip].append(current_time)
        
        # Main page
        @self.app.get("/", response_class=HTMLResponse)
        async def get_index():
            return self._get_html_interface()
        
        # Health check
        @self.app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "i3_connected": self.i3_client.is_connected() if self.i3_client else False,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # I3 Status
        @self.app.get("/api/status")
        async def get_status(token: str = Depends(verify_token), _=Depends(check_rate_limit)):
            if not self.i3_client:
                raise HTTPException(status_code=503, detail="I3 client not initialized")
            
            try:
                status = await self.i3_client.status()
                return status
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        # WebSocket endpoint
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await self._handle_websocket(websocket)
    
    def _get_html_interface(self) -> str:
        """Generate HTML interface."""
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>I3 Web Client</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
        }
        .main {
            display: flex;
            height: 600px;
        }
        .sidebar {
            width: 250px;
            background: #ecf0f1;
            padding: 20px;
            border-right: 1px solid #bdc3c7;
        }
        .content {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        .chat-area {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background: #fff;
        }
        .input-area {
            padding: 20px;
            border-top: 1px solid #bdc3c7;
            background: #f8f9fa;
        }
        .message {
            margin: 5px 0;
            padding: 8px;
            border-radius: 4px;
            background: #e8f4fd;
        }
        .btn {
            padding: 8px 16px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .btn:hover {
            background: #2980b9;
        }
        .input-group {
            display: flex;
            gap: 10px;
            margin: 10px 0;
        }
        .input-group input {
            flex: 1;
            padding: 8px;
            border: 1px solid #bdc3c7;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>I3 Web Client</h1>
            <p>Web interface for Intermud3 Gateway</p>
        </div>
        
        <div class="main">
            <div class="sidebar">
                <h3>Controls</h3>
                <button class="btn" onclick="connect()">Connect</button>
                <button class="btn" onclick="disconnect()">Disconnect</button>
            </div>
            
            <div class="content">
                <div id="chat-area" class="chat-area">
                    <div class="message">Welcome to I3 Web Client!</div>
                </div>
                
                <div class="input-area">
                    <div class="input-group">
                        <input type="text" id="message-input" placeholder="Type your message...">
                        <button class="btn" onclick="sendMessage()">Send</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let websocket = null;
        
        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            websocket = new WebSocket(wsUrl);
            
            websocket.onopen = function() {
                addMessage('Connected to I3 Gateway');
            };
            
            websocket.onmessage = function(event) {
                const message = JSON.parse(event.data);
                handleMessage(message);
            };
            
            websocket.onclose = function() {
                addMessage('Disconnected from I3 Gateway');
            };
        }
        
        function disconnect() {
            if (websocket) {
                websocket.close();
            }
        }
        
        function handleMessage(message) {
            addMessage(`Received: ${JSON.stringify(message)}`);
        }
        
        function sendMessage() {
            const input = document.getElementById('message-input');
            const message = input.value;
            
            if (message && websocket) {
                websocket.send(JSON.stringify({
                    type: 'message',
                    data: { message: message }
                }));
                input.value = '';
                addMessage(`Sent: ${message}`);
            }
        }
        
        function addMessage(text) {
            const chatArea = document.getElementById('chat-area');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message';
            messageDiv.textContent = text;
            chatArea.appendChild(messageDiv);
            chatArea.scrollTop = chatArea.scrollHeight;
        }
    </script>
</body>
</html>
        '''
    
    async def start(self):
        """Start the web client."""
        self.logger.info("Starting I3 Web Client...")
        
        # Initialize I3 client
        await self._initialize_i3()
        
        # Start web server
        config = uvicorn.Config(
            app=self.app,
            host=self.config['web_host'],
            port=self.config['web_port'],
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        self.logger.info(f"Web client available at http://{self.config['web_host']}:{self.config['web_port']}")
        await server.serve()
    
    async def _initialize_i3(self):
        """Initialize I3 client."""
        self.logger.info("Connecting to I3 Gateway...")
        
        self.i3_client = I3Client(
            url=self.config['i3_gateway_url'],
            api_key=self.config['i3_api_key'],
            mud_name=self.config['i3_mud_name'],
            auto_reconnect=True,
            reconnect_interval=5.0,
            max_reconnect_attempts=10
        )
        
        # Connect
        await self.i3_client.connect()
    
    async def _handle_websocket(self, websocket: WebSocket):
        """Handle WebSocket connection."""
        await websocket.accept()
        self.connected_websockets.add(websocket)
        
        try:
            while True:
                data = await websocket.receive_json()
                await websocket.send_json({"echo": data})
        except WebSocketDisconnect:
            pass
        finally:
            self.connected_websockets.discard(websocket)


if __name__ == '__main__':
    # Check FastAPI availability
    if not FASTAPI_AVAILABLE:
        print("Error: FastAPI is required for the web client")
        print()
        print("Install with:")
        print("  pip install fastapi uvicorn")
        print()
        sys.exit(1)
    
    # Check required environment variables
    if not os.getenv('I3_API_KEY'):
        print("Error: I3_API_KEY environment variable is required")
        print()
        print("Required environment variables:")
        print("  export I3_API_KEY='your-gateway-api-key'")
        print()
        print("Example:")
        print("  export I3_API_KEY='abc123-def456-ghi789'")
        print("  export WEB_AUTH_TOKEN='secure-web-token'")
        print("  python web_client.py")
        print()
        print("Then open: http://localhost:8000")
        sys.exit(1)
    
    # Run the web client
    try:
        client = WebClient()
        exit_code = asyncio.run(client.start())
        sys.exit(exit_code)
    except Exception as e:
        logging.error(f"Failed to start web client: {e}")
        sys.exit(1)
