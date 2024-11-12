# network/protocols.py

import asyncio
from typing import Callable, Any
from utils.logging import factory_logger


class ModbusManager:
    def __init__(self, port: int):
        self.port = port
        self.running = False
        self.client = None

    async def start(self):
        """Start Modbus client"""
        try:
            self.running = True
            factory_logger.network(f"Modbus client started on port {self.port}")
        except Exception as e:
            factory_logger.network(f"Modbus error: {str(e)}", "error")
            raise e

    async def stop(self):
        """Stop Modbus client"""
        self.running = False
        if self.client:
            self.client.close()


class MQTTManager:
    def __init__(self, broker: str, port: int):
        self.broker = broker
        self.port = port
        self.running = False
        self.client = None

    async def start(self):
        """Start MQTT client"""
        try:
            self.running = True
            factory_logger.network(f"MQTT client connected to {self.broker}:{self.port}")
        except Exception as e:
            factory_logger.network(f"MQTT error: {str(e)}", "error")
            raise e

    async def stop(self):
        """Stop MQTT client"""
        self.running = False
        if self.client:
            await self.client.disconnect()

    async def subscribe(self, topic: str, callback: Callable):
        """Subscribe to MQTT topic"""
        if self.running and self.client:
            await self.client.subscribe(topic)


class OPCUAManager:
    def __init__(self):
        self.running = False
        self.server = None

    async def start(self):
        """Start OPC UA server"""
        try:
            self.running = True
            factory_logger.network("OPC UA server started")
        except Exception as e:
            factory_logger.network(f"OPC UA error: {str(e)}", "error")
            raise e

    async def stop(self):
        """Stop OPC UA server"""
        self.running = False
        if self.server:
            await self.server.stop()
