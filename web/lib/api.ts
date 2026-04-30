"use client";

export type Role = "admin" | "user";

export interface User {
  id: string;
  email: string;
  role: Role;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AppSettings {
  provider: string;
  model_name: string;
  system_prompt: string;
  enabled_tools: string[];
  updated_at: string;
}

export interface FileOut {
  id: string;
  filename: string;
  content_type: string;
  summary: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface MessageOut {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  attachments: FileOut[];
  created_at: string;
}

export interface ConversationOut {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatResponse {
  conversation: ConversationOut;
  message: MessageOut;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const TOKEN_KEY = "assistant_token";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function storeToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export async function login(email: string, password: string) {
  return apiFetch<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: { email, password }
  });
}

export async function register(email: string, password: string) {
  return apiFetch<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: { email, password }
  });
}

export async function me(token: string) {
  return apiFetch<User>("/api/auth/me", { token });
}

export async function listConversations(token: string) {
  return apiFetch<ConversationOut[]>("/api/chat/conversations", { token });
}

export async function listMessages(token: string, conversationId: string) {
  return apiFetch<MessageOut[]>(`/api/chat/conversations/${conversationId}/messages`, { token });
}

export async function sendMessage(token: string, input: { message: string; conversation_id?: string | null; file_ids: string[] }) {
  return apiFetch<ChatResponse>("/api/chat", {
    method: "POST",
    token,
    body: input
  });
}

export async function uploadFile(token: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch<FileOut>("/api/files/upload", {
    method: "POST",
    token,
    formData
  });
}

export async function readSettings(token: string) {
  return apiFetch<AppSettings>("/api/settings", { token });
}

export async function saveSettings(token: string, settings: Pick<AppSettings, "model_name" | "system_prompt" | "enabled_tools">) {
  return apiFetch<AppSettings>("/api/settings", {
    method: "PUT",
    token,
    body: settings
  });
}

export async function listTools(token: string) {
  return apiFetch<{ available: string[]; enabled: string[] }>("/api/tools", { token });
}

async function apiFetch<T>(
  path: string,
  options: {
    method?: string;
    token?: string | null;
    body?: unknown;
    formData?: FormData;
  } = {}
): Promise<T> {
  const headers: HeadersInit = {};
  if (options.token) headers.Authorization = `Bearer ${options.token}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method || "GET",
    headers,
    body: options.formData || (options.body !== undefined ? JSON.stringify(options.body) : undefined)
  });

  if (!response.ok) {
    let detail = `Request failed with ${response.status}`;
    try {
      const data = await response.json();
      detail = typeof data.detail === "string" ? data.detail : detail;
    } catch {
      // Keep the status fallback.
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

