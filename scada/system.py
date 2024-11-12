# scada/system.py

from typing import Dict, Any, List
import asyncio
from datetime import datetime
import logging
from network.protocols import ModbusManager, MQTTManager, OPCUAManager
import uuid
import time
from config import Config


class SCADASystem:
    def __init__(self, config: Config):
        self.config = config.simulation
        self.running = False
        self.device_states = {}
        self.alarms = []
        self.historical_data = []

        # Initialize network managers
        self.modbus = ModbusManager(self.config.MODBUS_PORT)
        self.mqtt = MQTTManager(self.config.MQTT_BROKER, self.config.MQTT_PORT)
        self.opcua = OPCUAManager()

        # Initialize logging
        self.logger = logging.getLogger("SCADA")
        self.logger.setLevel(logging.INFO)

        # Add new monitoring parameters
        self.monitoring_params = {
            "level_threshold_high": 95.0,
            "level_threshold_low": 5.0,
            "motor_speed_max": 1.2,
            "stale_data_timeout": 30,
            "process_timeout": 300,
        }

        # Add performance metrics
        self.metrics = {
            "total_bottles": 0,
            "successful_bottles": 0,
            "failed_bottles": 0,
            "average_cycle_time": 0,
            "current_throughput": 0,
        }

    async def start(self):
        """Start all communication protocols"""
        tasks = [self.mqtt.start(), self.opcua.start(), self.modbus.start()]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            factory_logger.system(f"SCADA system error: {str(e)}", "error")
            # Update all statuses to disconnected on error
            dashboard_api.update_status("modbus", False)
            dashboard_api.update_status("mqtt", False)
            dashboard_api.update_status("opcua", False)
            raise e

        # Set up MQTT subscriptions
        await self.setup_subscriptions()

        # Start main monitoring loop
        asyncio.create_task(self._monitoring_loop())

    async def stop(self):
        """Stop SCADA system"""
        self.running = False

        # Stop network protocols
        await asyncio.gather(self.modbus.stop(), self.mqtt.stop(), self.opcua.stop())

    async def setup_subscriptions(self):
        """Set up MQTT subscriptions for all sensors"""
        await self.mqtt.subscribe("factory/sensors/#", self._handle_sensor_data)
        await self.mqtt.subscribe("factory/actuators/#", self._handle_actuator_data)

    async def _handle_sensor_data(self, data: Dict[str, Any]):
        """Handle incoming sensor data"""
        sensor_id = data.get("sensor_id")
        if sensor_id:
            self.device_states[sensor_id] = data
            await self._process_sensor_data(data)
            await self._store_historical_data("sensor", data)

    async def _handle_actuator_data(self, data: Dict[str, Any]):
        """Handle incoming actuator data"""
        actuator_id = data.get("actuator_id")
        if actuator_id:
            self.device_states[actuator_id] = data
            await self._process_actuator_data(data)
            await self._store_historical_data("actuator", data)

    async def _process_sensor_data(self, data: Dict[str, Any]):
        """Process sensor data and generate alarms if needed"""
        sensor_type = data.get("type")
        sensor_id = data.get("sensor_id")

        if sensor_type == "level":
            level = data.get("level", 0)
            if level > self.monitoring_params["level_threshold_high"]:
                await self._create_alarm(
                    "HIGH_LEVEL",
                    f"High level detected in {sensor_id}: {level}%",
                    severity="warning",
                )
            elif level < self.monitoring_params["level_threshold_low"]:
                await self._create_alarm(
                    "LOW_LEVEL",
                    f"Low level detected in {sensor_id}: {level}%",
                    severity="warning",
                )

        elif sensor_type == "proximity":
            # Monitor for stuck bottles
            if data.get("detected", False):
                last_change = data.get("last_change", 0)
                if (
                    time.time() - last_change
                    > self.monitoring_params["process_timeout"]
                ):
                    await self._create_alarm(
                        "STUCK_BOTTLE",
                        f"Bottle stuck at {sensor_id}",
                        severity="critical",
                    )

    async def _process_actuator_data(self, data: Dict[str, Any]):
        """Process actuator data and check for anomalies"""
        actuator_type = data.get("type")

        if actuator_type == "motor":
            # Check motor speed limits
            speed = data.get("speed", 0)
            if speed > data.get("max_speed", 1.0):
                await self._create_alarm(
                    "HIGH_SPEED", f"Motor speed exceeds limit in {data['actuator_id']}"
                )

    async def _create_alarm(
        self, alarm_type: str, message: str, severity: str = "warning"
    ):
        """Create and store an alarm"""
        alarm = {
            "id": str(uuid.uuid4()),
            "type": alarm_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "acknowledged": False,
        }

        self.alarms.append(alarm)
        self.logger.warning(f"Alarm [{severity}]: {message}")

        # Store in historical data
        await self._store_historical_data("alarm", alarm)

        # Publish alarm to MQTT
        await self.mqtt.publish("factory/alarms", alarm)

    async def _store_historical_data(self, data_type: str, data: Dict[str, Any]):
        """Store historical data"""
        historical_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": data_type,
            "data": data,
        }
        self.historical_data.append(historical_entry)

        # Limit historical data size
        if len(self.historical_data) > 10000:
            self.historical_data = self.historical_data[-10000:]

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Update OPC UA variables with current states
                for device_id, state in self.device_states.items():
                    await self.opcua.update_variable(device_id, state)

                # Check for stale data
                current_time = datetime.now()
                for device_id, state in self.device_states.items():
                    last_update = datetime.fromisoformat(state.get("timestamp"))
                    if (current_time - last_update).total_seconds() > 30:
                        await self._create_alarm(
                            "STALE_DATA", f"No updates from {device_id} for 30 seconds"
                        )

                await asyncio.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)

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

    def get_device_state(self, device_id: str) -> Dict[str, Any]:
        """Get current state of a specific device"""
        return self.device_states.get(device_id)

    def get_active_alarms(self) -> List[Dict[str, Any]]:
        """Get list of active alarms"""
        return [alarm for alarm in self.alarms if not alarm["acknowledged"]]

    def acknowledge_alarm(self, alarm_id: str):
        """Acknowledge an alarm"""
        for alarm in self.alarms:
            if alarm.get("id") == alarm_id:
                alarm["acknowledged"] = True
                self.logger.info(f"Alarm {alarm_id} acknowledged")
                break
