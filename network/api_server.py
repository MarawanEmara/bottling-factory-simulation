from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import time
from datetime import datetime
from utils.logging import factory_logger


class DashboardAPI:
    def __init__(self):
        self.app = FastAPI()
        self.active_connections: list[WebSocket] = []
        self.factory = None  # Will be set when initializing

        # Initialize system status
        self.system_status = {
            "modbus": False,
            "mqtt": False,
            "opcua": False,
            "last_update": datetime.now().isoformat(),
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
                    # Get current factory status
                    status = self.factory.get_status()

                    # Get bottle states distribution
                    bottle_states = {}
                    for bottle in self.factory.bottles_in_progress.queue:
                        state = bottle["state"]
                        bottle_states[state] = bottle_states.get(state, 0) + 1

                    # Get recent logs
                    recent_logs = (
                        factory_logger.get_recent_logs()
                    )  # You'll need to implement this

                    # Send data to client
                    await websocket.send_json(
                        {
                            "process": status,
                            "bottleStates": bottle_states,
                            "logs": recent_logs,
                            "stats": {
                                "throughput": self.factory.metrics["successful_bottles"]
                                / ((time.time() - self.factory.start_time) / 60),
                                "error_rate": self.factory.metrics["failed_bottles"]
                                / (
                                    self.factory.metrics["successful_bottles"]
                                    + self.factory.metrics["failed_bottles"]
                                    or 1
                                ),
                            },
                        }
                    )

                    await asyncio.sleep(1)  # Update every second

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

        @self.app.post("/api/control/{station}/{action}")
        async def control_station(station: str, action: str):
            if not self.factory:
                return {"error": "Factory not initialized"}

            try:
                if station in ["filling", "capping", "labeling"]:
                    actuator_map = {
                        "filling": "filling_valve",
                        "capping": "capping_actuator",
                        "labeling": "labeling_motor",
                    }

                    actuator = self.factory.actuators[actuator_map[station]]

                    if action == "start":
                        actuator.activate()
                    elif action == "stop":
                        actuator.deactivate()
                    elif action.startswith("speed_"):
                        if hasattr(actuator, "set_speed"):
                            speed = float(action.split("_")[1])
                            actuator.set_speed(speed)

                    return {
                        "status": "success",
                        "message": f"{station} {action} completed",
                    }
                else:
                    return {"error": "Invalid station"}, 400

            except Exception as e:
                factory_logger.system(f"Control error: {str(e)}", "error")
                return {"error": str(e)}, 500

    def set_factory(self, factory):
        """Set factory instance for control operations"""
        self.factory = factory

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
