# scada/hmi.py

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from utils.logging import factory_logger
import asyncio
import json
from typing import Dict, Set
import uvicorn
import time


class HMIServer:
    def __init__(self, scada_system, factory):
        self.app = FastAPI()
        self.scada = scada_system
        self.factory = factory
        self.active_connections: Set[WebSocket] = set()
        self.update_interval = 0.1  # 100ms updates
        self.server = None
        self.broadcast_task = None

        self._setup_routes()
        self._setup_websocket()
        self.app.mount("/static", StaticFiles(directory="static"), name="static")

    async def start(self):
        """Start the HMI server"""
        try:
            # Start broadcast task
            self.broadcast_task = asyncio.create_task(self._broadcast_updates())

            # Configure server
            config = uvicorn.Config(
                self.app,
                host="127.0.0.1",
                port=8001,  # Different port from API server
                loop="asyncio",
            )
            self.server = uvicorn.Server(config)

            # Start server
            await self.server.serve()

        except Exception as e:
            factory_logger.system(f"Error starting HMI server: {str(e)}", "error")
            raise

    async def shutdown(self):
        """Shutdown the HMI server"""
        try:
            # Cancel broadcast task
            if self.broadcast_task:
                self.broadcast_task.cancel()
                try:
                    await self.broadcast_task
                except asyncio.CancelledError:
                    pass

            # Close all websocket connections
            for connection in self.active_connections:
                await connection.close()
            self.active_connections.clear()

            # Shutdown server
            if self.server:
                self.server.should_exit = True
                await self.server.shutdown()

            factory_logger.system("HMI server shutdown complete")

        except Exception as e:
            factory_logger.system(f"Error shutting down HMI server: {str(e)}", "error")

    def _setup_websocket(self):
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.active_connections.add(websocket)
            try:
                while True:
                    # Keep connection alive and wait for any client messages
                    data = await websocket.receive_text()
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)
            except Exception as e:
                if websocket in self.active_connections:
                    self.active_connections.remove(websocket)

    def _setup_routes(self):
        @self.app.get("/")
        async def root():
            return {"status": "HMI Server Running"}

        @self.app.get("/status")
        async def get_status():
            return {
                "factory": self.factory.get_status(),
                "scada": {"alarms": self.scada.alarms, "metrics": self.factory.metrics},
            }

        @self.app.get("/api/process")
        async def get_process_data():
            """Get detailed process data for visualization"""
            return {
                "bottles": [
                    bottle.__dict__ for bottle in self.factory.process.bottles.values()
                ],
                "stations": {
                    "filling": {
                        "level": self.factory.sensors["level_filling"].current_level,
                        "valve_state": self.factory.actuators["filling_valve"].state,
                        "busy": self.factory.process.station_locks["filling"].locked(),
                    },
                    "capping": {
                        "actuator_state": self.factory.actuators[
                            "capping_actuator"
                        ].state,
                        "busy": self.factory.process.station_locks["capping"].locked(),
                    },
                    "labeling": {
                        "motor_speed": self.factory.actuators[
                            "labeling_motor"
                        ].current_speed,
                        "busy": self.factory.process.station_locks["labeling"].locked(),
                    },
                },
                "conveyor_speed": self.factory.actuators["main_conveyor"].current_speed,
            }

        @self.app.post("/api/control/{station}/{action}")
        async def control_station(station: str, action: str):
            """Control station actuators"""
            try:
                if action == "start":
                    if station == "filling":
                        await self.factory.start()
                    elif station == "capping":
                        self.factory.actuators["capping_actuator"].activate()
                    elif station == "labeling":
                        self.factory.actuators["labeling_motor"].activate()
                elif action == "stop":
                    if station == "filling":
                        await self.factory.stop()
                    elif station == "capping":
                        self.factory.actuators["capping_actuator"].deactivate()
                    elif station == "labeling":
                        self.factory.actuators["labeling_motor"].deactivate()

                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    async def _broadcast_updates(self):
        """Broadcast real-time updates to all connected clients"""
        while True:
            if self.active_connections:
                # Calculate elapsed time safely
                elapsed_time = max(1, time.time() - self.factory.start_time)

                update = {
                    "process": {
                        "bottles": list(self.factory.bottles_in_progress.queue),
                        "stations": {
                            "filling": {
                                "level": self.factory.sensors[
                                    "level_filling"
                                ].last_reading,
                                "busy": self.factory.process.station_locks[
                                    "filling"
                                ].locked(),
                            },
                            "capping": {
                                "actuator_state": self.factory.actuators[
                                    "capping_actuator"
                                ].is_active,
                                "busy": self.factory.process.station_locks[
                                    "capping"
                                ].locked(),
                            },
                            "labeling": {
                                "motor_speed": self.factory.actuators[
                                    "labeling_motor"
                                ].current_speed,
                                "busy": self.factory.process.station_locks[
                                    "labeling"
                                ].locked(),
                            },
                        },
                        "conveyor_speed": self.factory.actuators[
                            "main_conveyor"
                        ].current_speed,
                    },
                    "stats": {
                        "throughput": self.factory.bottles_produced
                        / elapsed_time
                        * 60,  # bottles per minute
                        "error_rate": len(
                            [
                                b
                                for b in self.factory.bottles_in_progress.queue
                                if b["state"] == "ERROR"
                            ]
                        )
                        / max(1, self.factory.bottles_produced),
                    },
                    "alarms": self.scada.alarms,
                }

                # Broadcast to all connections
                for connection in self.active_connections:
                    try:
                        await connection.send_json(update)
                    except:
                        self.active_connections.remove(connection)

            await asyncio.sleep(self.update_interval)
