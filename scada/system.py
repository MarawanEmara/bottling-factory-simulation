# scada/system.py

from typing import Dict, Any, List
import asyncio
from datetime import datetime
import logging
from network.protocols import ModbusManager, MQTTManager, OPCUAManager
from utils.logging import factory_logger
import uuid
from config import Config


class SCADASystem:
    def __init__(self, config: Config):
        """Initialize SCADA system with configuration"""
        self.config = config.simulation
        self.running = False
        self.device_states = {}
        self.alarms = []
        self.historical_data = []
        self.monitoring_task = None
        self.protocols = None  # Will be set later

        # Define monitoring parameters
        self.monitoring_params = {
            "level_threshold_high": 95.0,
            "level_threshold_low": 5.0,
            "motor_speed_max": 1.2,
            "stale_data_timeout": 30,
        }

    def set_protocols(self, protocols: dict):
        """Set protocol instances"""
        self.protocols = protocols
        self.modbus = protocols["modbus"]
        self.mqtt = protocols["mqtt"]
        self.opcua = protocols["opcua"]

    async def start(self):
        """Start SCADA system"""
        try:
            if not self.protocols:
                raise Exception("Protocols not set")

            # Set up MQTT subscriptions
            await self.mqtt.subscribe("factory/sensors/#", self._handle_sensor_data)
            await self.mqtt.subscribe("factory/actuators/#", self._handle_actuator_data)

            # Start monitoring loop
            self.running = True
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())

            factory_logger.system("SCADA system started successfully")

        except Exception as e:
            factory_logger.system(f"Error starting SCADA system: {str(e)}", "error")
            await self.stop()
            raise

    async def stop(self):
        """Stop SCADA system"""
        try:
            factory_logger.system("Initiating SCADA system shutdown...")

            # Stop monitoring loop
            self.running = False
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass

            factory_logger.system("SCADA system shutdown complete")

        except Exception as e:
            factory_logger.system(f"Error during SCADA shutdown: {str(e)}", "error")
            raise

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                current_time = datetime.now()

                # Update OPC UA variables
                for device_id, state in self.device_states.items():
                    try:
                        await self.opcua.update_variable(device_id, state)
                    except Exception as e:
                        factory_logger.system(
                            f"Error updating OPC UA variable: {str(e)}", "error"
                        )

                # Check for stale data
                for device_id, state in self.device_states.items():
                    try:
                        # Handle different timestamp formats/types
                        timestamp = state.get("timestamp")
                        if isinstance(timestamp, (int, float)):
                            # Convert Unix timestamp to datetime
                            last_update = datetime.fromtimestamp(timestamp)
                        elif isinstance(timestamp, str):
                            # Parse ISO format string
                            last_update = datetime.fromisoformat(timestamp)
                        elif isinstance(timestamp, datetime):
                            # Already datetime object
                            last_update = timestamp
                        else:
                            # Skip if timestamp is invalid
                            continue

                        if (
                            current_time - last_update
                        ).total_seconds() > self.monitoring_params[
                            "stale_data_timeout"
                        ]:
                            await self._create_alarm(
                                "STALE_DATA",
                                f"No updates from {device_id} for {self.monitoring_params['stale_data_timeout']} seconds",
                            )
                    except Exception as e:
                        factory_logger.system(
                            f"Error checking stale data for {device_id}: {str(e)}",
                            "error",
                        )

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                factory_logger.system(f"Error in monitoring loop: {str(e)}", "error")
                await asyncio.sleep(5)

    async def _create_alarm(
        self, alarm_type: str, message: str, severity: str = "warning"
    ):
        """Create and store an alarm"""
        try:
            alarm = {
                "id": str(uuid.uuid4()),
                "type": alarm_type,
                "message": message,
                "severity": severity,
                "timestamp": datetime.now().isoformat(),
                "acknowledged": False,
            }

            self.alarms.append(alarm)
            factory_logger.system(f"Alarm [{severity}]: {message}")

            # Store in historical data
            await self._store_historical_data("alarm", alarm)

            # Publish alarm to MQTT
            await self.mqtt.publish("factory/alarms", alarm)

        except Exception as e:
            factory_logger.system(f"Error creating alarm: {str(e)}", "error")

    async def _handle_sensor_data(self, data: Dict[str, Any]):
        """Handle incoming sensor data"""
        try:
            sensor_id = data.get("sensor_id")
            if sensor_id:
                self.device_states[sensor_id] = data
                await self._process_sensor_data(data)
                await self._store_historical_data("sensor", data)
        except Exception as e:
            factory_logger.system(f"Error handling sensor data: {str(e)}", "error")

    async def _handle_actuator_data(self, data: Dict[str, Any]):
        """Handle incoming actuator data"""
        try:
            actuator_id = data.get("actuator_id")
            if actuator_id:
                self.device_states[actuator_id] = data
                await self._process_actuator_data(data)
                await self._store_historical_data("actuator", data)
        except Exception as e:
            factory_logger.system(f"Error handling actuator data: {str(e)}", "error")

    async def _store_historical_data(self, data_type: str, data: Dict[str, Any]):
        """Store historical data with size limit"""
        try:
            historical_entry = {
                "timestamp": datetime.now().isoformat(),
                "type": data_type,
                "data": data,
            }
            self.historical_data.append(historical_entry)

            # Limit historical data size
            if len(self.historical_data) > 10000:
                self.historical_data = self.historical_data[-10000:]

        except Exception as e:
            factory_logger.system(f"Error storing historical data: {str(e)}", "error")

    def get_status(self) -> Dict[str, Any]:
        """Get current SCADA system status"""
        return {
            "running": self.running,
            "device_count": len(self.device_states),
            "alarm_count": len(self.alarms),
            "unacknowledged_alarms": sum(
                1 for alarm in self.alarms if not alarm["acknowledged"]
            ),
            "last_update": datetime.now().isoformat(),
        }

    def acknowledge_alarm(self, alarm_id: str):
        """Acknowledge an alarm"""
        try:
            for alarm in self.alarms:
                if alarm.get("id") == alarm_id:
                    alarm["acknowledged"] = True
                    factory_logger.system(f"Alarm {alarm_id} acknowledged")
                    break
        except Exception as e:
            factory_logger.system(f"Error acknowledging alarm: {str(e)}", "error")

    async def _process_sensor_data(self, data: Dict[str, Any]):
        """Process incoming sensor data"""
        try:
            sensor_id = data.get("sensor_id")
            value = data.get("value")

            # Extract value from dictionary if needed
            if isinstance(value, dict):
                value = value.get("value", False)

            # Convert to appropriate type based on sensor ID
            if sensor_id.startswith("proximity_"):
                value = bool(value)
            elif sensor_id.startswith("level_"):
                value = float(value)

            # Update OPC UA variable with properly typed value
            if self.opcua.running:
                await self.opcua.update_variable(sensor_id, value)

        except Exception as e:
            factory_logger.system(f"Error processing sensor data: {str(e)}", "error")

    async def _process_actuator_data(self, data: Dict[str, Any]):
        """Process incoming actuator data"""
        try:
            actuator_id = data.get("actuator_id")
            actuator_type = data.get("type")
            command = data.get("command")

            # Check for motor speed limits
            if actuator_type == "motor" and "speed" in data:
                speed = data["speed"]
                if speed > self.monitoring_params["motor_speed_max"]:
                    await self._create_alarm(
                        "HIGH_SPEED",
                        f"High speed detected in {actuator_id}: {speed}",
                        "warning",
                    )

            # Update OPC UA variable if server is running
            if self.opcua.running:
                try:
                    await self.opcua.update_variable(actuator_id, data)
                except Exception as e:
                    factory_logger.system(
                        f"Error updating OPC UA variable: {str(e)}", "error"
                    )

        except Exception as e:
            factory_logger.system(f"Error processing actuator data: {str(e)}", "error")
