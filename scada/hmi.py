# scada/hmi.py

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
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

        self._setup_routes()
        self._setup_websocket()
        self.app.mount("/static", StaticFiles(directory="static"), name="static")

        # Start broadcast task
        asyncio.create_task(self._broadcast_updates())

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

    def start(self, host: str = "localhost", port: int = 8000):
        """Start the HMI server"""
        # Start update broadcast task
        asyncio.create_task(self._broadcast_updates())

        # Start FastAPI server
        uvicorn.run(self.app, host=host, port=port)
