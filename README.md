# bottling-factory-simulation

# Industrial Bottling Factory Simulation

A sophisticated simulation of an industrial bottling factory that demonstrates industrial automation protocols (Modbus TCP, MQTT, OPC UA) and PLC-based control systems.

## Overview

This project simulates a complete bottling production line with the following stations:

- Filling Station
- Capping Station
- Labeling Station

The system implements a full industrial automation stack:

```mermaid
graph TB
    subgraph Supervisory["Supervisory Layer"]
        SCADA["SCADA System"]
        HMI["HMI Interface"]
    end

    subgraph Control["Control Layer"]
        PLCs["PLCs"]
    end

    subgraph Field["Field Layer"]
        Devices["Sensors & Actuators"]
    end

    %% Protocol Labels
    SCADA <--> |"OPC UA"| PLCs
    SCADA <-.-> |"MQTT"| Devices
    PLCs <--> |"Modbus TCP"| Devices
    HMI <--> |"OPC UA"| SCADA

    classDef protocol fill:#f9f,stroke:#333,stroke-width:2px
    class MQTT,OPC,Modbus protocol

```

## Architecture

### Supervisory Layer

- SCADA System for process monitoring and control
- HMI Interface for operator interaction
- OPC UA communication with PLCs
- MQTT telemetry for sensor data

### Control Layer

- Dedicated PLCs for each station:
  - Filling PLC
  - Capping PLC
  - Labeling PLC
  - Conveyor PLC
- Modbus TCP communication with field devices

### Field Layer

- Sensors:
  - Proximity sensors for bottle detection
  - Level sensors for fill monitoring
- Actuators:
  - Control valves
  - Conveyor motors
  - Capping actuators
  - Labeling motors

## Network Architecture

The system implements three industrial protocols:

1. **Modbus TCP**

   - Field device communication
   - Sensor readings and actuator control
   - Register-based data exchange

2. **MQTT**

   - Telemetry data collection
   - Asynchronous sensor updates
   - Real-time monitoring

3. **OPC UA**
   - PLC to SCADA communication
   - Structured data model
   - Secure, reliable data exchange

## Process Flow

The bottling process follows this sequence:

```mermaid
flowchart TB
    Start([Start]) --> PS1{Bottle Detected?}
    PS1 -->|"Modbus TCP"| Fill

    subgraph Filling ["Filling Process"]
        Fill[Start Fill] -->|"OPC UA"| SCADA1[SCADA Start Fill]
        SCADA1 --> OpenV[Open Valve]
        OpenV -->|"Modbus TCP"| MonitorL[Monitor Level]
        MonitorL --> LevelOK{Level OK?}
        LevelOK -->|No| MonitorL
        LevelOK -->|Yes| CloseV[Close Valve]
        CloseV -->|"OPC UA"| FillComplete[Fill Complete]
    end

    FillComplete --> PS2{Bottle at Capper?}
    PS2 -->|"Modbus TCP"| Cap

    subgraph Capping ["Capping Process"]
        Cap[Start Cap] -->|"OPC UA"| SCADA2[SCADA Start Cap]
        SCADA2 -->|"Modbus TCP"| ActCap[Activate Capper]
        ActCap --> CapOK{Cap Applied?}
        CapOK -->|No| ActCap
        CapOK -->|Yes| CapComplete[Cap Complete]
        CapComplete -->|"OPC UA"| CapDone[Cap Done]
    end

    CapDone --> PS3{Bottle at Labeler?}
    PS3 -->|"Modbus TCP"| Label

    subgraph Labeling ["Labeling Process"]
        Label[Start Label] -->|"OPC UA"| SCADA3[SCADA Start Label]
        SCADA3 -->|"Modbus TCP"| ActLabel[Activate Labeler]
        ActLabel --> LabelOK{Label Applied?}
        LabelOK -->|No| ActLabel
        LabelOK -->|Yes| LabelComplete[Label Complete]
        LabelComplete -->|"OPC UA"| LabelDone[Label Done]
    end

    LabelDone --> End([End])

    subgraph SCADA ["SCADA System"]
        HMI[HMI Interface]
        SCADA_System[SCADA Controller]
        HMI <-->|"OPC UA"| SCADA_System
    end

    SCADA_System -.->|"OPC UA"| SCADA1
    SCADA_System -.->|"OPC UA"| SCADA2
    SCADA_System -.->|"OPC UA"| SCADA3

    %% Styling
    classDef process fill:#bbf,stroke:#333,stroke-width:2px
    classDef decision fill:#fbb,stroke:#333,stroke-width:2px
    classDef scada fill:#dbf,stroke:#333,stroke-width:2px
    classDef endpoint fill:#dfd,stroke:#333,stroke-width:2px

    class Fill,Cap,Label,ActCap,ActLabel,OpenV,CloseV,MonitorL process
    class PS1,PS2,PS3,LevelOK,CapOK,LabelOK decision
    class SCADA1,SCADA2,SCADA3,SCADA_System,HMI scada
    class Start,End endpoint
```

## Features

- Real-time simulation of industrial processes
- Multi-protocol network communication
- Packet capture and analysis
- SCADA system with HMI interface
- Comprehensive logging system
- Error handling and fault detection
- Production metrics and analytics

## Getting Started

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure settings in `config/settings.py`

3. Run the simulation:

```bash
python main.py
```

4. Access the HMI interface at `http://localhost:8001`

## Network Monitoring

The system captures network traffic for analysis:

- Modbus packets: `captures/modbus_traffic.pcap`
- MQTT packets: `captures/mqtt_traffic.pcap`
- OPC UA packets: `captures/opcua_traffic.pcap`

## Logging

Comprehensive logging is available in the `logs` directory:

- Network communication
- Process events
- System status
- Error conditions

## Configuration

Key parameters can be adjusted in `config/settings.py`:

- Timing settings
- Network ports
- Station positions
- Simulation speed

## Development

The project is structured into several key components:

- `devices/`: PLC and field device implementations
- `network/`: Protocol managers and packet capture
- `scada/`: SCADA system and HMI interface
- `simulation/`: Core process simulation
- `utils/`: Logging and helper functions
