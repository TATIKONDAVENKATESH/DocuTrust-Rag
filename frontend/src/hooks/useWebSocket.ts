import { useRef, useCallback, useState } from "react";
import type { Citation, WsMessageType } from "../types";

interface WsHookReturn {
  logs: string[];
  isConnected: boolean;
  isBusy: boolean;
  sendQuery: (
    query: string,
    onResult: (answer: string, citations: Citation[], logs: string[]) => void,
    onError: (msg: string) => void
  ) => void;
  clearLogs: () => void;
}

export function useWebSocket(token: string | null): WsHookReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isBusy, setIsBusy] = useState(false);

  // Stable refs for callbacks so we don't close over stale values
  const onResultRef = useRef<((answer: string, citations: Citation[], logs: string[]) => void) | null>(null);
  const onErrorRef = useRef<((msg: string) => void) | null>(null);
  const collectedLogsRef = useRef<string[]>([]);

  const sendQuery = useCallback(
    (
      query: string,
      onResult: (answer: string, citations: Citation[], logs: string[]) => void,
      onError: (msg: string) => void
    ) => {
      if (!token) {
        onError("Not authenticated.");
        return;
      }

      onResultRef.current = onResult;
      onErrorRef.current = onError;
      collectedLogsRef.current = [];
      setLogs([]);
      setIsBusy(true);

      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const host = window.location.host;
      const wsUrl = `${protocol}://${host}/ws/chat?token=${token}`;

      // Close any stale socket
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        if (wsRef.current.readyState === WebSocket.OPEN ||
            wsRef.current.readyState === WebSocket.CONNECTING) {
          wsRef.current.close();
        }
      }

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        ws.send(JSON.stringify({ query }));
      };

      ws.onmessage = (event: MessageEvent) => {
        let msg: WsMessageType;
        try {
          msg = JSON.parse(event.data as string);
        } catch {
          return;
        }

        if (msg.type === "ping") return;

        if (msg.type === "start") {
          collectedLogsRef.current = [];
          setLogs([]);
        } else if (msg.type === "log") {
          collectedLogsRef.current = [...collectedLogsRef.current, msg.message];
          setLogs([...collectedLogsRef.current]);
        } else if (msg.type === "result") {
          setIsBusy(false);
          onResultRef.current?.(msg.answer, msg.citations, msg.agent_logs);
        } else if (msg.type === "error") {
          setIsBusy(false);
          onErrorRef.current?.(msg.message);
        }
      };

      ws.onerror = () => {
        setIsConnected(false);
        setIsBusy(false);
        onErrorRef.current?.("WebSocket connection failed. Please try again.");
      };

      ws.onclose = (event: CloseEvent) => {
        setIsConnected(false);
        setIsBusy(false);
        // code 4001 = auth failure
        if (event.code === 4001) {
          onErrorRef.current?.("Authentication failed. Please log in again.");
        }
      };
    },
    [token]
  );

  const clearLogs = useCallback(() => {
    setLogs([]);
    collectedLogsRef.current = [];
  }, []);

  return { logs, isConnected, isBusy, sendQuery, clearLogs };
}