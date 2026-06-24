import { useState, useCallback } from "react";
import { ShieldCheck, LogOut } from "lucide-react";
import { DocumentPanel } from "../components/DocumentPanel";
import { AgentLogPanel } from "../components/AgentLogPanel";
import { ChatPanel } from "../components/ChatPanel";
import { useAuth } from "../hooks/useAuth";

export function WorkspacePage() {
  const { user, logout } = useAuth();
  const [agentLogs, setAgentLogs] = useState<string[]>([]);
  const [wsConnected, setWsConnected] = useState(false);

  const handleNewLogs = useCallback((logs: string[]) => {
    setAgentLogs(logs);
  }, []);

  const handleConnectionChange = useCallback((connected: boolean) => {
    setWsConnected(connected);
  }, []);

  const clearLogs = useCallback(() => setAgentLogs([]), []);

  return (
    <div className="flex flex-col h-screen bg-slate-950">
      {/* Top bar */}
      <header className="flex items-center px-4 py-2.5 border-b border-slate-800 shrink-0 gap-3">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center">
            <ShieldCheck className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-white tracking-tight">DocuTrust</span>
          <span className="text-xs text-slate-600 ml-1">Enterprise RAG</span>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <span className="text-xs text-slate-500">{user?.email}</span>
          <button onClick={logout} className="btn-ghost" title="Sign out">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Three-panel layout */}
      <div className="flex flex-1 gap-3 p-3 min-h-0">
        {/* Left: Documents */}
        <div className="w-72 shrink-0">
          <DocumentPanel />
        </div>

        {/* Middle: Agent logs */}
        <div className="w-80 shrink-0">
          <AgentLogPanel
            logs={agentLogs}
            isConnected={wsConnected}
            onClear={clearLogs}
          />
        </div>

        {/* Right: Chat */}
        <div className="flex-1 min-w-0">
          <ChatPanel
            onLogsUpdate={handleNewLogs}
            onConnectionChange={handleConnectionChange}
          />
        </div>
      </div>
    </div>
  );
}