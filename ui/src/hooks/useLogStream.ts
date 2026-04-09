import { useEffect, useRef, useState } from "react";
import type { LogEvent } from "../types/api";

export function useLogStream(maxLines = 200) {
  const [lines, setLines] = useState<LogEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${proto}://${window.location.host}/ws/log`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as LogEvent;
        if (data.event === "ping") return;
        setLines((prev) => [...prev.slice(-(maxLines - 1)), data]);
      } catch {
        // ignore malformed
      }
    };

    return () => ws.close();
  }, [maxLines]);

  const clear = () => setLines([]);
  return { lines, clear };
}
