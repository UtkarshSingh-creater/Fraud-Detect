/*
import { useEffect, useState } from "react";
import { io } from "socket.io-client";

export default function useSocket() {
  const [risk, setRisk] = useState(0);
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState({});

  useEffect(() => {
    const socket = io("http://localhost:8000");

    socket.on("risk_update", (data) => setRisk(data.score));
    socket.on("event_log", (e) => setEvents((prev) => [e, ...prev]));
    socket.on("status_update", (s) => setStatus(s));

    return () => socket.disconnect();
  }, []);

  return { risk, events, status };
}*/
import { useEffect, useState } from "react";

export default function useSocket(sessionId) {
  const [risk, setRisk] = useState(0);
  const [events, setEvents] = useState([]);
  const [riskLevel, setRiskLevel] = useState("LOW");
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/dashboard');

    ws.onopen = () => {
      setConnected(true);
      console.log("Dashboard connected to backend");};

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.session_id === sessionId) {
      setRisk(data.risk_score);
      setRiskLevel(data.risk_level);
      setEvents(prev => [data.latest_event, ... prev].slice(0, 100));
      }
    };

    ws. onclose = () => setConnected(false);
    ws. onerror = (e) => console.error("WS error", e);

    // Keep alive ping
    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, 30000);

    return () => {
      clearInterval(ping);
      ws.close();
    };

  }, [sessionId]);

  return { risk, riskLevel, events, connected };
}

