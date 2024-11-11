# config/settings.py


class SimulationConfig:
    # Simulation parameters
    SIMULATION_SPEED = 1.0  # 1.0 = real-time, 2.0 = 2x speed, etc.
    BOTTLE_INTERVAL = 2.0  # Time between bottles in seconds

    # Process parameters
    FILL_TIME = 3.0  # Time to fill one bottle
    CAP_TIME = 1.0  # Time to cap one bottle
    LABEL_TIME = 1.5  # Time to label one bottle

    # Network parameters
    MODBUS_PORT = 5020
    MQTT_BROKER = "localhost"
    MQTT_PORT = 1883
    OPC_UA_PORT = 4840

    # Device parameters
    SENSOR_UPDATE_RATE = 0.1  # Seconds between sensor updates

    # Logging
    LOG_LEVEL = "INFO"
    LOG_FILE = "factory_simulation.log"


class FactoryLayout:
    # Physical layout parameters
    CONVEYOR_LENGTH = 100  # Length in units
    STATION_POSITIONS = {"filling": 25, "capping": 50, "labeling": 75}

    # Sensor positions
    SENSOR_POSITIONS = {
        "entry": 0,
        "pre_fill": 20,
        "post_fill": 30,
        "pre_cap": 45,
        "post_cap": 55,
        "pre_label": 70,
        "post_label": 80,
        "exit": 100,
    }
