import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "../api.js";

/**
 * EventSource hook with auto-reconnect and connection health monitoring.
 * Listens to GET /api/stream/alerts and dispatches parsed alerts to onAlert callback.
 */
export function useAlertsStream({ onAlert, minTier = null, enabled = true } = {}) {
  const [status, setStatus] = useState("Connecting"); // "Live" | "Reconnecting" | "Disconnected"
  const [lastHeartbeat, setLastHeartbeat] = useState(null);
  const esRef = useRef(null);
  const onAlertRef = useRef(onAlert);
  onAlertRef.current = onAlert;

  const connect = useCallback(() => {
    if (!enabled) return;

    if (esRef.current) {
      esRef.current.close();
    }

    const url = api.getAlertsStreamUrl(minTier);
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setStatus("Live");
      setLastHeartbeat(new Date());
    };

    es.onmessage = (event) => {
      setLastHeartbeat(new Date());
      if (!event.data) return;

      try {
        const payload = JSON.parse(event.data);
        if (payload && payload.employee_id && onAlertRef.current) {
          onAlertRef.current(payload);
        }
      } catch (err) {
        // SSE comments or non-JSON messages
      }
    };

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        setStatus("Disconnected");
      } else {
        // EventSource will automatically retry in background
        setStatus("Reconnecting");
      }
    };
  }, [minTier, enabled]);

  useEffect(() => {
    connect();
    return () => {
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [connect]);

  return {
    status,
    lastHeartbeat,
    reconnect: connect,
  };
}
