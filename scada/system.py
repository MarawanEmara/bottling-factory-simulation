# scada/system.py

from typing import Dict, Any, List
import asyncio
from datetime import datetime
import logging
from network.protocols import ModbusManager, MQTTManager, OPCUAManager


class SCADASystem:
    def __init__(self, config):
        self.config = config
        self.running = False
        self.device_states = {}
        self.alarms = []
        self.historical_data = []

        # Initialize network managers
        self.modbus = ModbusManager(config.MODBUS_PORT)
        self.mqtt = MQTTManager(config.MQTT_BROKER, config.MQTT_PORT)
        self.opcua = OPCUAManager()

        # Initialize logging
        self.logger = logging.getLogger("SCADA")
        self.logger.setLevel(logging.INFO)

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

        if sensor_type == "level":
            # Check fill level limits
            level = data.get("level", 0)
            if level > 95:
                await self._create_alarm(
                    "HIGH_LEVEL",
                    f"High level detected in {data['sensor_id']}: {level}%",
                )
            elif level < 5:
                await self._create_alarm(
                    "LOW_LEVEL", f"Low level detected in {data['sensor_id']}: {level}%"
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

    async def _create_alarm(self, alarm_type: str, message: str):
        """Create and store an alarm"""
        alarm = {
            "type": alarm_type,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "acknowledged": False,
        }
        self.alarms.append(alarm)
        self.logger.warning(f"Alarm: {message}")

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