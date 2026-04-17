import { useEffect, useRef, useState } from 'react';

import { wsUrl } from '../config/api';

const MAX_EVENTS = 200;
const RECONNECT_DELAY_MS = 2000;

export function useWorkloadWS(workloadId) {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState(workloadId ? 'connecting' : 'idle');
  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const shouldReconnectRef = useRef(true);

  useEffect(() => {
    setEvents([]);

    if (!workloadId) {
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      if (socketRef.current && socketRef.current.readyState <= WebSocket.OPEN) {
        socketRef.current.close();
      }
      setStatus('idle');
      return () => undefined;
    }

    shouldReconnectRef.current = true;

    const connect = () => {
      setStatus((current) => (current === 'connected' ? current : 'connecting'));
      const socket = new WebSocket(wsUrl(`/ws/${workloadId}`));
      socketRef.current = socket;

      socket.onopen = () => {
        setStatus('connected');
      };

      socket.onmessage = (message) => {
        try {
          const parsed = JSON.parse(message.data);
          setEvents((previous) => [parsed, ...previous].slice(0, MAX_EVENTS));
        } catch (error) {
          console.error('Failed to parse WebSocket event', error);
        }
      };

      socket.onclose = () => {
        if (!shouldReconnectRef.current) {
          setStatus('idle');
          return;
        }
        setStatus('reconnecting');
        reconnectTimerRef.current = window.setTimeout(connect, RECONNECT_DELAY_MS);
      };

      socket.onerror = () => {
        socket.close();
      };
    };

    connect();

    return () => {
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      if (socketRef.current && socketRef.current.readyState <= WebSocket.OPEN) {
        socketRef.current.close();
      }
    };
  }, [workloadId]);

  return { events, status };
}

export default useWorkloadWS;
