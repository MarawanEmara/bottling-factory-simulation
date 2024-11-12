import React, { useState } from "react";
import useWebSocket from "react-use-websocket";
import {
  Container,
  Paper,
  Typography,
  Grid,
  Box,
  CircularProgress,
} from "@mui/material";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Brush,
  BarChart,
  Bar,
} from "recharts";

const WS_URL = "ws://localhost:8000/ws";

function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [timeSeriesData, setTimeSeriesData] = useState([]);
  const [bottleStates, setBottleStates] = useState({});

  const { sendMessage } = useWebSocket(WS_URL, {
    onOpen: () => setIsConnected(true),
    onClose: () => setIsConnected(false),
    onMessage: (message) => {
      try {
        const data = JSON.parse(message.data);
        if (data) {
          setTimeSeriesData(prev => [...prev, {
            timestamp: new Date().toLocaleTimeString(),
            // Station status
            filling: data.process?.stations?.filling?.busy ? 1 : 0,
            capping: data.process?.stations?.capping?.busy ? 1 : 0,
            labeling: data.process?.stations?.labeling?.busy ? 1 : 0,
            // Performance metrics
            throughput: data.stats?.throughput || 0,
            errorRate: (data.stats?.error_rate || 0) * 100,
            bottlesInProgress: data.process?.bottles?.length || 0,
            // Station metrics
            fillLevel: data.process?.stations?.filling?.level || 0,
            cappingState: data.process?.stations?.capping?.actuator_state ? 1 : 0,
            labelingSpeed: data.process?.stations?.labeling?.motor_speed || 0,
            conveyorSpeed: data.process?.conveyor_speed || 0,
            // Station utilization
            fillingUtilization: data.stats?.station_utilization?.filling || 0,
            cappingUtilization: data.stats?.station_utilization?.capping || 0,
            labelingUtilization: data.stats?.station_utilization?.labeling || 0,
          }].slice(-50));
          
          setBottleStates(data.bottleStates || {});
        }
      } catch (e) {
        console.error("WebSocket message error:", e);
      }
    },
    shouldReconnect: () => true,
  });

  if (!isConnected) {
    return (
      <Container
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
        }}
      >
        <Box textAlign="center">
          <CircularProgress />
          <Typography sx={{ mt: 2 }}>
            Connecting to factory system...
          </Typography>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" gutterBottom>
        Bottling Factory Dashboard
      </Typography>

      <Grid container spacing={3}>
        {/* Station Status Chart */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Station Status
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={timeSeriesData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis domain={[0, 1]} />
                <Tooltip />
                <Legend />
                <Line type="stepAfter" dataKey="filling" stroke="#8884d8" name="Filling Station" />
                <Line type="stepAfter" dataKey="capping" stroke="#82ca9d" name="Capping Station" />
                <Line type="stepAfter" dataKey="labeling" stroke="#ffc658" name="Labeling Station" />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Performance Metrics */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Performance Metrics
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={timeSeriesData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="throughput" stroke="#ff7300" name="Throughput (bottles/min)" />
                <Line type="monotone" dataKey="errorRate" stroke="#ff0000" name="Error Rate (%)" />
                <Line type="monotone" dataKey="bottlesInProgress" stroke="#00ff00" name="Bottles in Progress" />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Station Metrics */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Station Metrics
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={timeSeriesData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="fillLevel" stroke="#8884d8" name="Fill Level (%)" />
                <Line type="stepAfter" dataKey="cappingState" stroke="#82ca9d" name="Capping Actuator" />
                <Line type="monotone" dataKey="labelingSpeed" stroke="#ffc658" name="Labeling Speed" />
                <Line type="monotone" dataKey="conveyorSpeed" stroke="#ff7300" name="Conveyor Speed" />
                <Brush dataKey="timestamp" height={30} stroke="#8884d8" />
              </LineChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>

        {/* Bottle States Distribution */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Bottle States Distribution
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={Object.entries(bottleStates).map(([state, count]) => ({
                state,
                count
              }))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="state" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#8884d8" name="Number of Bottles" />
              </BarChart>
            </ResponsiveContainer>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
}

export default App;
