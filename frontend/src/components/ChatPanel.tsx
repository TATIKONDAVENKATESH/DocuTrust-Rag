import { useState, useRef, useEffect, FormEvent, useCallback } from "react";
import { MessageSquare, Send, User, Bot, Loader2, AlertCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CitationList } from "./CitationList";
import type { Citation, RetrievedChunkPreview } from "../types";
import { useWebSocket } from "../hooks/useWebSocket";
import { useAuth } from "../hooks/useAuth";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  confidence?: number;
  usedWebFallback?: boolean;
  retrievedChunks?: RetrievedChunkPreview[];
  error?: boolean;
}

interface ChatPanelProps {
  onLogsUpdate: (logs: string[]) => void;
  onConnectionChange: (connected: boolean) => void;
}

export function ChatPanel({ onLogsUpdate, onConnectionChange }: ChatPanelProps) {
  const { token } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  const { sendQuery, logs, isConnected, isBusy, clearLogs } = useWebSocket(token);

  // Forward logs to parent for the AgentLogPanel
  useEffect(() => {
    onLogsUpdate(logs);
  }, [logs, onLogsUpdate]);

  // Forward WebSocket connection state to parent
  useEffect(() => {
    onConnectionChange(isConnected);
  }, [isConnected, onConnectionChange]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isBusy]);

  const handleSubmit = useCallback(
    (e: FormEvent) => {
      e.preventDefault();
      const q = input.trim();
      if (!q || isBusy) return;

      setInput("");
      clearLogs();

      const userMsg: Message = {
        id: `u-${Date.now()}`,
        role: "user",
        content: q,
        citations: [],
      };
      setMessages((prev) => [...prev, userMsg]);

      sendQuery(
        q,
        // onResult
        (answer, citations, _logs, confidence, usedWebFallback, retrievedChunks) => {
          const assistantMsg: Message = {
            id: `a-${Date.now()}`,
            role: "assistant",
            content: answer,
            citations,
            confidence,
            usedWebFallback,
            retrievedChunks,
          };
          setMessages((prev) => [...prev, assistantMsg]);
        },
        // onError
        (errMsg) => {
          const errorMsg: Message = {
            id: `e-${Date.now()}`,
            role: "assistant",
            content: errMsg,
            citations: [],
            error: true,
          };
          setMessages((prev) => [...prev, errorMsg]);
        }
      );
    },
    [input, isBusy, sendQuery, clearLogs]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as FormEvent);
    }
  };

  return (
    <div className="panel h-full">
      <div className="panel-header">
        <MessageSquare className="w-4 h-4 text-brand-400" />
        Chat
        <span className="ml-auto text-xs text-slate-600 font-normal">
          {messages.filter((m) => m.role === "user").length} queries
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-700">
            <Bot className="w-10 h-10" />
            <p className="text-sm">Ask anything about your documents</p>
            <p className="text-xs text-slate-600">
              Answers are grounded with citations from uploaded files
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
          >
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
                msg.role === "user" ? "bg-brand-600" : msg.error ? "bg-red-900" : "bg-slate-700"
              }`}
            >
              {msg.role === "user" ? (
                <User className="w-3.5 h-3.5 text-white" />
              ) : msg.error ? (
                <AlertCircle className="w-3.5 h-3.5 text-red-400" />
              ) : (
                <Bot className="w-3.5 h-3.5 text-slate-300" />
              )}
            </div>

            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
                msg.role === "user"
                  ? "bg-brand-600 text-white rounded-tr-sm"
                  : msg.error
                  ? "bg-red-950/50 border border-red-900 text-red-300 rounded-tl-sm"
                  : "bg-slate-800 text-slate-100 rounded-tl-sm"
              }`}
            >
              <div className="prose prose-invert prose-sm max-w-none break-words">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
              </div>
              {msg.role === "assistant" && !msg.error && msg.citations.length > 0 && (
                <CitationList
                  citations={msg.citations}
                  confidence={msg.confidence}
                  usedWebFallback={msg.usedWebFallback}
                  retrievedChunks={msg.retrievedChunks}
                />
              )}
            </div>
          </div>
        ))}

        {isBusy && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center shrink-0 mt-0.5">
              <Bot className="w-3.5 h-3.5 text-slate-300" />
            </div>
            <div className="bg-slate-800 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-2 text-slate-400 text-sm">
              <Loader2 className="w-4 h-4 animate-spin text-brand-400" />
              <span>Running CRAG pipeline…</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="p-3 border-t border-slate-800 shrink-0">
        <div className="flex gap-2 items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your documents… (Enter to send, Shift+Enter for newline)"
            disabled={isBusy}
            rows={1}
            className="input-field flex-1 resize-none leading-relaxed"
            style={{ minHeight: "40px", maxHeight: "120px" }}
          />
          <button
            onClick={(e) => handleSubmit(e as unknown as FormEvent)}
            disabled={isBusy || !input.trim()}
            className="btn-primary px-3 py-2 shrink-0"
            title="Send"
          >
            {isBusy ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}