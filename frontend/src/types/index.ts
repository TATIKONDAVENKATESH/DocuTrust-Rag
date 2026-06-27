export interface User {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
}

export interface AuthState {
  token: string | null;
  user: User | null;
}

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  chunk_count: number;
  uploaded_at: string;
  status: "processing" | "ready" | "error";
  error?: string | null; // populated by backend when status === "error"
}

export interface Citation {
  filename: string;
  page_number: number | null;
  chunk_id: string;
  relevance_score?: number | null;
  text_preview?: string | null;
}

export interface RetrievedChunkPreview {
  filename: string;
  page_number: number | null;
  text_preview: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  created_at: string;
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
}

export interface QueryResponse {
  session_id: string;
  answer: string;
  citations: Citation[];
  agent_trace: string[];
  confidence: number;
  used_web_fallback: boolean;
}

export type WsMessageType =
  | { type: "start"; query: string }
  | { type: "log"; message: string }
  | {
      type: "result";
      answer: string;
      citations: Citation[];
      agent_logs: string[];
      confidence: number;
      used_web_fallback: boolean;
      retrieved_chunks: RetrievedChunkPreview[];
    }
  | { type: "error"; message: string }
  | { type: "ping" };