from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
from datetime import datetime
from utils.logging import factory_logger

class DashboardAPI:
    def __init__(self):
        self.app = FastAPI()
        self.active_connections: list[WebSocket] = []
        self.system_status = {
            "modbus": False,
            "mqtt": False,
            "opcua": False,
            "last_update": None
        }
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self.setup_routes()
    
    def setup_routes(self):
        @self.app.get("/")
        async def root():
            return {"message": "Factory Dashboard API"}
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)
            try:
                while True:
                    # Send status updates every second
                    await websocket.send_json(self.system_status)
                    await asyncio.sleep(1)
            except Exception as e:
                factory_logger.system(f"WebSocket error: {str(e)}", "error")
            finally:
                if websocket in self.active_connections:
                    self.active_connections.remove(websocket)
        
        @self.app.get("/status")
        async def get_status():
            return self.system_status
        
        @self.app.get("/logs")
        async def get_logs():
            return {"logs": ["System started", "API server running"]}
    
    def update_status(self, protocol: str, connected: bool):
        """Update system status and broadcast to all clients"""
        self.system_status[protocol] = connected
        self.system_status["last_update"] = datetime.now().isoformat()
        
        # Broadcast to all connected websocket clients
        for connection in self.active_connections:
            try:
                asyncio.create_task(connection.send_json(self.system_status))
            except:
                if connection in self.active_connections:
                    self.active_connections.remove(connection)

# Create global instance
dashboard_api = DashboardAPI()
