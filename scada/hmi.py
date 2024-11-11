# scada/hmi.py

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
import asyncio
import json
from typing import Dict, Set
import uvicorn


class HMIServer:
    def __init__(self, scada_system, factory):
        self.app = FastAPI()
        self.scada = scada_system
        self.factory = factory
        self.active_connections: Set[WebSocket] = set()

        self._setup_routes()
        self.app.mount("/static", StaticFiles(directory="static"), name="static")

    def _setup_routes(self):
        @self.app.get("/api/status")
        async def get_status():
            return {
                "scada": self.scada.get_status(),
                "factory": self.factory.get_status(),
                "process": self.factory.process.get_status(),
            }

        @self.app.get("/api/alarms")
        async def get_alarms():
            return {
                "active": self.scada.get_active_alarms(),
                "history": self.scada.alarms[-100:],  # Last 100 alarms
            }

        @self.app.post("/api/alarms/{alarm_id}/acknowledge")
        async def acknowledge_alarm(alarm_id: str):
            self.scada.acknowledge_alarm(alarm_id)
            return {"status": "success"}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_connections.add(websocket)

            try:
                while True:
                    # Receive commands from client
                    data = await websocket.receive_json()
                    await self._handle_ws_command(websocket, data)
            except:
                self.active_connections.remove(websocket)

    async def _handle_ws_command(self, websocket: WebSocket, data: Dict):
        """Handle WebSocket commands from clients"""
        command = data.get("command")

        if command == "start_factory":
            await self.factory.start()
        elif command == "stop_factory":
            await self.factory.stop()
        elif command == "adjust_speed":
            speed = data.get("speed", 1.0)
            self.factory.actuators["main_conveyor"].set_speed(speed)

    async def broadcast_updates(self):
        """Broadcast updates to all connected clients"""
        while True:
            if self.active_connections:
                update = {
                    "timestamp": time.time(),
                    "status": await self.app.get_status(),
                    "alarms": len(self.scada.get_active_alarms()),
                }

                for connection in self.active_connections:
                    try:
                        await connection.send_json(update)
                    except:
                        self.active_connections.remove(connection)

            await asyncio.sleep(1)

    def start(self, host: str = "localhost", port: int = 8000):
        """Start the HMI server"""
        # Start update broadcast task
        asyncio.create_task(self.broadcast_updates())

        # Start FastAPI server
        uvicorn.run(self.app, host=host, port=port)
