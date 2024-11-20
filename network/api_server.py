from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import time
from datetime import datetime
from utils.logging import factory_logger
import uvicorn


class DashboardAPI:
    def __init__(self):
        self.app = FastAPI()
        self.factory = None
        self.server = None
        self._setup_routes()

    def set_factory(self, factory):
        """Set factory instance after initialization"""
        self.factory = factory

    async def start(self):
        """Start the API server"""
        try:
            # Configure server
            config = uvicorn.Config(
                self.app, host="127.0.0.1", port=8000, loop="asyncio"
            )
            self.server = uvicorn.Server(config)
            # Start server
            await self.server.serve()
        except Exception as e:
            factory_logger.system(f"Error starting API server: {str(e)}", "error")
            raise

    async def shutdown(self):
        """Shutdown the API server"""
        try:
            if self.server:
                self.server.should_exit = True
                await self.server.shutdown()
                factory_logger.system("API server shutdown complete")
        except Exception as e:
            factory_logger.system(f"Error shutting down API server: {str(e)}", "error")

    def _setup_routes(self):
        @self.app.get("/")
        async def root():
            return {"status": "API Server Running"}

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

                    # Send data to client
                    await websocket.send_json(
                        {
                            "process": {
                                **status,
                                "stations": {
                                    "filling": {
                                        "busy": status["stations"]["filling"]["busy"],
                                        "level": status["stations"]["filling"]["level"],
                                        "valve_state": status["stations"]["filling"][
                                            "valve_state"
                                        ],
                                    },
                                    "capping": {
                                        "busy": status["stations"]["capping"]["busy"],
                                        "actuator_state": status["stations"]["capping"][
                                            "actuator_state"
                                        ],
                                    },
                                    "labeling": {
                                        "busy": status["stations"]["labeling"]["busy"],
                                        "motor_speed": status["stations"]["labeling"][
                                            "motor_speed"
                                        ],
                                    },
                                },
                                "conveyor_speed": status["conveyor_speed"],
                            },
                            "bottleStates": bottle_states,
                            "stats": {
                                "throughput": self.factory.metrics["successful_bottles"]
                                / ((time.time() - self.factory.start_time) / 60),
                                "error_rate": self.factory.metrics["failed_bottles"]
                                / (
                                    self.factory.metrics["successful_bottles"]
                                    + self.factory.metrics["failed_bottles"]
                                    or 1
                                ),
                                "average_fill_level": self.factory.metrics[
                                    "average_fill_level"
                                ],
                                "average_labeling_speed": self.factory.metrics[
                                    "average_labeling_speed"
                                ],
                                "average_conveyor_speed": self.factory.metrics[
                                    "average_conveyor_speed"
                                ],
                                "station_utilization": self.factory.metrics[
                                    "station_utilization"
                                ],
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
            if not self.factory:
                return {"error": "Factory not initialized"}
            return self.factory.get_status()

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
