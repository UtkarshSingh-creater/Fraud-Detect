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
}