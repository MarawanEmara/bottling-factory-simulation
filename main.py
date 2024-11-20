import asyncio
import signal
import uvicorn
from config import Config
from simulation.factory import BottlingFactory
from network.api_server import DashboardAPI
from scada.system import SCADASystem
from scada.hmi import HMIServer
from utils.logging import factory_logger
from network.protocols import ModbusManager, OPCUAManager, MQTTManager


class ApplicationManager:
    def __init__(self):
        self.config = Config()
        self.protocols = None
        self.scada = None
        self.factory = None
        self.api_server = None
        self.hmi = None

    async def initialize(self):
        """Initialize all components in correct order"""
        try:
            # 1. Initialize protocols first
            factory_logger.system("Initializing protocols...")
            self.protocols = {
                "modbus": ModbusManager(self.config.simulation.MODBUS_SERVER_PORT),
                "mqtt": MQTTManager(
                    self.config.simulation.MQTT_BROKER, self.config.simulation.MQTT_PORT
                ),
                "opcua": OPCUAManager(),
            }

            # 2. Start protocols
            for name, protocol in self.protocols.items():
                factory_logger.system(f"Starting {name} protocol...")
                await protocol.start()
                factory_logger.system(f"{name} protocol started successfully")

            # 3. Initialize SCADA with config and protocols
            self.scada = SCADASystem(self.config)
            self.scada.set_protocols(self.protocols)  # Pass existing protocol instances
            await self.scada.start()

            # 4. Initialize Factory
            self.factory = BottlingFactory(self.config, self.scada, self.protocols)
            await self.factory.initialize()

            # 5. Initialize API and HMI
            self.api_server = DashboardAPI()
            self.api_server.set_factory(self.factory)
            self.hmi = HMIServer(self.scada, self.factory)

            factory_logger.system("All components initialized successfully")

        except Exception as e:
            factory_logger.system(f"Initialization error: {str(e)}", "error")
            await self.shutdown()
            raise

    async def start(self):
        """Start all components"""
        try:
            # Start factory
            if self.factory:
                await self.factory.start()

            # Start SCADA
            if self.scada:
                await self.scada.start()

            # Start API and HMI servers
            if self.api_server:
                await self.api_server.start()
            if self.hmi:
                await self.hmi.start()

            factory_logger.system("All components started successfully")

        except Exception as e:
            factory_logger.system(f"Error starting components: {str(e)}", "error")
            await self.shutdown()
            raise

    async def shutdown(self):
        """Shutdown all components in reverse order"""
        factory_logger.system("Initiating graceful shutdown...")

        try:
            # Stop API and HMI first
            if self.api_server:
                await self.api_server.shutdown()
            if self.hmi:
                await self.hmi.shutdown()

            # Stop factory
            if self.factory:
                await self.factory.stop()

            # Stop SCADA
            if self.scada:
                await self.scada.stop()

            # Stop protocols last
            if self.protocols:
                for protocol in self.protocols.values():
                    await protocol.stop()

            factory_logger.system("Shutdown complete")

        except Exception as e:
            factory_logger.system(f"Error during shutdown: {str(e)}", "error")
            raise


async def main():
    app_manager = ApplicationManager()

    try:
        await app_manager.initialize()
        await app_manager.start()
    except Exception as e:
        factory_logger.system(f"Application error: {str(e)}", "error")
    finally:
        await app_manager.shutdown()


def handle_shutdown(signum, frame):
    """Handle shutdown signals"""
    factory_logger.system(f"Received signal {signum}")
    loop = asyncio.get_event_loop()
    loop.stop()


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        factory_logger.system("Received keyboard interrupt")
    except Exception as e:
        factory_logger.system(f"Unexpected error: {str(e)}", "error")
