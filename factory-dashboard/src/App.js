import React, { useState, useEffect } from "react";
import useWebSocket from "react-use-websocket";
import {
  Container,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  Chip,
  Alert,
} from "@mui/material";

const WS_URL = "ws://localhost:8000/ws";
const API_URL = "http://localhost:8000";

function App() {
  const [status, setStatus] = useState({
    modbus: false,
    mqtt: false,
    opcua: false,
    last_update: null,
  });
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState(null);

  const { lastJsonMessage } = useWebSocket(WS_URL, {
    onMessage: (message) => {
      try {
        const data = JSON.parse(message.data);
        setStatus(data);
      } catch (e) {
        console.error('WebSocket message error:', e);
      }
    },
    onError: () => {
      setError('WebSocket connection failed');
    },
    shouldReconnect: () => true,
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch initial status
        const statusRes = await fetch(`${API_URL}/status`);
        const statusData = await statusRes.json();
        setStatus(statusData);
        setError(null);
      } catch (e) {
        setError('Failed to connect to API server');
        console.error('API error:', e);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000);
    
    return () => clearInterval(interval);
  }, []);

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        Bottling Factory Dashboard
      </Typography>
      
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      <Grid container spacing={3}>
        {/* Status Cards */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              System Status
            </Typography>
            <Grid container spacing={2}>
              {Object.entries(status).map(([key, value]) => {
                if (key === "last_update") return null;
                return (
                  <Grid item xs={4} key={key}>
                    <Card>
                      <CardContent>
                        <Typography variant="h6">
                          {key.toUpperCase()}
                        </Typography>
                        <Chip
                          label={value ? "Connected" : "Disconnected"}
                          color={value ? "success" : "error"}
                        />
                      </CardContent>
                    </Card>
                  </Grid>
                );
              })}
            </Grid>
          </Paper>
        </Grid>

        {/* Logs */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2, height: 400, overflow: "auto" }}>
            <Typography variant="h6" gutterBottom>
              System Logs
            </Typography>
            <List>
              {logs.map((log, index) => (
                <ListItem key={index}>
                  <ListItemText primary={log} />
                </ListItem>
              ))}
            </List>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
}

export default App;
