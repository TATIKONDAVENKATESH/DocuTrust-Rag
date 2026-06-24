import axios from "axios";
import type { User, Document, ChatMessage, Session, QueryResponse } from "../types";

const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("docutrust_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ── Auth ──────────────────────────────────────────────────────────────────

export async function register(
  email: string,
  password: string,
  full_name: string
): Promise<{ access_token: string; user: User }> {
  const { data } = await api.post("/auth/register", { email, password, full_name });
  return data;
}

export async function login(
  email: string,
  password: string
): Promise<{ access_token: string; user: User }> {
  const form = new FormData();
  form.append("username", email);
  form.append("password", password);
  const { data } = await api.post("/auth/login", form);
  return data;
}

export async function getMe(): Promise<User> {
  const { data } = await api.get("/auth/me");
  return data;
}

// ── Documents ─────────────────────────────────────────────────────────────

export async function uploadDocument(file: File): Promise<Document> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post("/documents/upload", form);
  return data;
}

export async function listDocuments(): Promise<Document[]> {
  const { data } = await api.get("/documents/");
  return data;
}

export async function deleteDocument(id: string): Promise<void> {
  await api.delete(`/documents/${id}`);
}

// ── Chat ──────────────────────────────────────────────────────────────────

export async function sendQuery(
  query: string,
  session_id?: string
): Promise<QueryResponse> {
  const { data } = await api.post("/chat/query", { query, session_id });
  return data;
}

export async function listSessions(): Promise<Session[]> {
  const { data } = await api.get("/chat/sessions");
  return data;
}

export async function getMessages(session_id: string): Promise<ChatMessage[]> {
  const { data } = await api.get(`/chat/sessions/${session_id}/messages`);
  return data;
}
