import asyncio
import uvicorn
from config import Config
from simulation.factory import BottlingFactory
from network.api_server import DashboardAPI
from scada.system import SCADASystem
from scada.hmi import HMIServer
from utils.logging import factory_logger


async def start_uvicorn(app):
    config = uvicorn.Config(app, host="localhost", port=8000, loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    # Initialize configuration
    config = Config()

    # Initialize components
    factory = BottlingFactory(config)
    scada = SCADASystem(config)

    # Initialize API and HMI servers
    api_server = DashboardAPI()
    api_server.set_factory(factory)

    hmi = HMIServer(scada, factory)

    # Configure HMI server
    hmi_config = uvicorn.Config(hmi.app, host="localhost", port=8001, loop="asyncio")
    hmi_server = uvicorn.Server(hmi_config)

    # Start all components
    tasks = [
        factory.start(),
        scada.start(),
        start_uvicorn(api_server.app),
        hmi_server.serve(),
    ]

    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        factory_logger.system(f"Application error: {str(e)}", "error")
    finally:
        await factory.stop()


if __name__ == "__main__":
    asyncio.run(main())
