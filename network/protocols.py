# network/protocols.py

import asyncio
from typing import Callable, Dict, Any
import json
from aiomqtt import Client as MQTTClient
from asyncua import Server as OPCUAServer, ua
from pymodbus.server.async_io import StartTcpServer, StartAsyncTcpServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from utils.logging import factory_logger


class NetworkManager:
    def __init__(self, config):
        self.config = config
        self.modbus_server = None
        self.mqtt_client = None
        self.opcua_server = None
        self.message_handlers = {}

    async def start_all(self):
        """Start all network protocols"""
        await asyncio.gather(self.start_modbus(), self.start_mqtt(), self.start_opcua())

    async def stop_all(self):
        """Stop all network protocols"""
        await asyncio.gather(self.stop_modbus(), self.stop_mqtt(), self.stop_opcua())


class ModbusManager:
    def __init__(self, port: int = 5020):
        self.port = port
        self.datastore = ModbusSlaveContext()
        self.context = ModbusServerContext(slaves=self.datastore, single=True)
        self.dashboard_api = dashboard_api  # Import from api_server

    async def start(self):
        """Start Modbus server"""
        try:
            self.dashboard_api.update_status("modbus", False)
            StartAsyncTcpServer(
                context=self.context,
                address=("localhost", self.port),
                allow_reuse_address=True
            )
            factory_logger.modbus(f"Server started on port {self.port}")
            self.dashboard_api.update_status("modbus", True)
        except Exception as e:
            factory_logger.modbus(f"Failed to start server: {e}", "error")
            self.dashboard_api.update_status("modbus", False)
            raise e

    async def stop(self):
        """Stop Modbus TCP server"""
        if self.server:
            self.server.shutdown()

    def update_register(self, address: int, value: int):
        """Update a holding register value"""
        self.datastore.setValues(3, address, [value])

    def read_register(self, address: int) -> int:
        """Read a holding register value"""
        return self.datastore.getValues(3, address, 1)[0]


class MQTTManager:
    def __init__(self, broker: str, port: int):
        self.broker = broker
        self.port = port
        self.client = None
        self.handlers = {}

    async def start(self):
        """Start MQTT client"""
        try:
            self.dashboard_api.update_status("mqtt", False)
            async with MQTTClient(hostname=self.broker, port=self.port) as client:
                self.client = client
                await client.subscribe("#")
                factory_logger.mqtt("Connected to broker")
                self.dashboard_api.update_status("mqtt", True)
                
                async for message in client.messages:
                    if message.topic.value in self.handlers:
                        await self.handlers[message.topic.value](message.payload)
        except Exception as e:
            factory_logger.mqtt(f"Connection failed: {str(e)}", "error")
            self.dashboard_api.update_status("mqtt", False)
            raise e

    async def stop(self):
        """Stop MQTT client"""
        if self.client:
            await self.client.disconnect()

    async def publish(self, topic: str, payload: dict):
        """Publish message to MQTT topic"""
        if self.client:
            await self.client.publish(topic, json.dumps(payload))

    async def subscribe(self, topic: str, handler):
        """Subscribe to MQTT topic"""
        if self.client:
            self.handlers[topic] = handler


class OPCUAManager:
    def __init__(self, endpoint: str = "opc.tcp://localhost:4840/"):
        self.endpoint = endpoint
        self.server = None
        self.nodes = {}

    async def start(self):
        """Start OPC UA server"""
        try:
            self.dashboard_api.update_status("opcua", False)
            self.server = OPCUAServer()
            await self.server.init()
            
            self.server.set_endpoint(self.endpoint)
            self.server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
            
            # Set up namespace
            uri = "http://examples.factory.opcua.com"
            idx = await self.server.register_namespace(uri)
            
            # Create object structure
            objects = self.server.nodes.objects
            self.factory_obj = await objects.add_object(idx, "BottlingFactory")
            
            await self.server.start()
            factory_logger.opcua(f"Server started at {self.endpoint}")
            self.dashboard_api.update_status("opcua", True)
            
        except Exception as e:
            factory_logger.opcua(f"Failed to start server: {e}", "error")
            self.dashboard_api.update_status("opcua", False)
            raise e

    async def stop(self):
        """Stop OPC UA server"""
        if self.server:
            await self.server.stop()

    async def create_variable(self, name: str, initial_value: Any):
        """Create a new OPC UA variable"""
        if self.server:
            var = await self.factory_obj.add_variable(
                self.server.nodes.objects.ns_index, name, initial_value
            )
            self.nodes[name] = var
            return var

    async def update_variable(self, name: str, value: Any):
        """Update an OPC UA variable value"""
        if name in self.nodes:
            await self.nodes[name].write_value(value)
