import { useRef, useCallback, useState } from "react";
import type { Citation, RetrievedChunkPreview, WsMessageType } from "../types";

type OnResultFn = (
  answer: string,
  citations: Citation[],
  logs: string[],
  confidence: number,
  usedWebFallback: boolean,
  retrievedChunks: RetrievedChunkPreview[],
  sessionId?: string
) => void;

interface WsHookReturn {
  logs: string[];
  isConnected: boolean;
  isBusy: boolean;
  sendQuery: (query: string, sessionId: string | undefined, onResult: OnResultFn, onError: (msg: string) => void) => void;
  clearLogs: () => void;
}

export function useWebSocket(token: string | null): WsHookReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isBusy, setIsBusy] = useState(false);

  // Stable refs for callbacks so we don't close over stale values
  const onResultRef = useRef<OnResultFn | null>(null);
  const onErrorRef = useRef<((msg: string) => void) | null>(null);
  const collectedLogsRef = useRef<string[]>([]);

  const sendQuery = useCallback(
    (query: string, sessionId: string | undefined, onResult: OnResultFn, onError: (msg: string) => void) => {
      if (!token) {
        onError("Not authenticated.");
        return;
      }

      onResultRef.current = onResult;
      onErrorRef.current = onError;
      collectedLogsRef.current = [];
      setLogs([]);
      setIsBusy(true);

      let wsUrl = "";
      const envApiUrl = import.meta.env.VITE_API_URL;
      
      if (envApiUrl && envApiUrl.startsWith("http")) {
        // e.g. https://my-backend.onrender.com/api -> wss://my-backend.onrender.com/ws/chat
        const wsProtocol = envApiUrl.startsWith("https") ? "wss" : "ws";
        const hostUrl = new URL(envApiUrl).host;
        wsUrl = `${wsProtocol}://${hostUrl}/ws/chat`;
      } else {
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        const host = window.location.host;
        wsUrl = `${protocol}://${host}/ws/chat`;
      }

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
        // [NOTE] Send auth frame first (avoids sending JWT in the URL query string)
        ws.send(JSON.stringify({ type: "auth", token }));
        // Then send query, including the optional sessionId for conversational memory
        ws.send(JSON.stringify({ query, session_id: sessionId }));
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
          // store session id for result callback? The backend also sends it if we need, but let's store it locally if we want.
          // For now, we will extract it from the result if needed or just pass it in result.
          // Wait, 'msg' type might not have session_id. Let's just handle it.
          if ((msg as any).session_id) {
             // We can keep track of the current session ID in a ref
             ws.sessionId = (msg as any).session_id;
          }
        } else if (msg.type === "log") {
          collectedLogsRef.current = [...collectedLogsRef.current, msg.message];
          setLogs([...collectedLogsRef.current]);
        } else if (msg.type === "result") {
          setIsBusy(false);
          onResultRef.current?.(
            msg.answer,
            msg.citations,
            msg.agent_logs,
            msg.confidence,
            msg.used_web_fallback,
            msg.retrieved_chunks,
            (ws as any).sessionId
          );
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