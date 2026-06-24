import { useEffect, useRef } from "react";
import { Terminal, Zap, Trash2 } from "lucide-react";

interface AgentLogPanelProps {
  logs: string[];
  isConnected: boolean;
  onClear: () => void;
}

function classifyLog(line: string): string {
  if (line.startsWith("ERROR")) return "text-red-400";
  if (line.includes("Rewriting") || line.includes("Rewritten")) return "text-yellow-400";
  if (line.includes("Relevance score")) return "text-cyan-400";
  if (line.includes("Generating") || line.includes("generated")) return "text-green-400";
  if (line.includes("Retrieved") || line.includes("Retrieving")) return "text-brand-400";
  if (line.includes("Relevant chunks")) return "text-purple-400";
  return "text-slate-400";
}

export function AgentLogPanel({ logs, isConnected, onClear }: AgentLogPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="panel h-full">
      <div className="panel-header">
        <Terminal className="w-4 h-4 text-green-400" />
        Agent Execution Log
        <span
          className={`ml-1 inline-block w-2 h-2 rounded-full ${
            isConnected ? "bg-green-400" : "bg-slate-600"
          }`}
          title={isConnected ? "WebSocket connected" : "Disconnected"}
        />
        <button onClick={onClear} className="btn-ghost ml-auto p-1" title="Clear logs">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 font-mono text-xs space-y-0.5">
        {logs.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-slate-700 gap-2">
            <Zap className="w-8 h-8" />
            <p>Agent logs will appear here</p>
            <p className="text-xs">Submit a query to start</p>
          </div>
        )}
        {logs.map((line, i) => (
          <div key={i} className={`log-line ${classifyLog(line)}`}>
            <span className="text-slate-700 mr-2 select-none">
              {String(i + 1).padStart(2, "0")}
            </span>
            {line}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
