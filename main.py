import asyncio
import uvicorn
import signal
from network.api_server import dashboard_api
from utils.logging import factory_logger

async def start_api_server():
    config = uvicorn.Config(
        app=dashboard_api.app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False  # Set to False for more stable WebSocket connections
    )
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    # Start API server
    api_task = asyncio.create_task(start_api_server())
    
    # Start your SCADA system
    factory_logger.system("Starting SCADA system")
    
    try:
        await api_task
    except asyncio.CancelledError:
        factory_logger.system("Shutting down gracefully")

if __name__ == "__main__":
    factory_logger.system("Application starting")
    asyncio.run(main())
