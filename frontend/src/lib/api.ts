export type SmtpSettings = { smtp_host: string; smtp_port: number; smtp_use_ssl: boolean; smtp_starttls: boolean; smtp_user: string; smtp_from: string; smtp_allowed_recipients: string[]; password_set: boolean; configured: boolean };
export type Source = { title: string; url: string; content: string; kind: string; text_url?: string; paragraph_start?: number; paragraph_end?: number };
export type Artifact = { id: string; filename: string };
export type Message = { id: string; role: string; content: string; metadata?: { sources?: Source[]; artifact?: Artifact; failed?: boolean } };
export type Conversation = { id: string; title: string };
export type BrainFile = { id: string; filename: string; type: string; status: string; error?: string; created_at?: string };
export type Job = { id: string; type: string; status: string; progress: number; error?: string };
export type Task = { id: string; title: string; level: string; owner?: string; deadline?: string; description: string; evidence: string; suggestion: string; status: string; email_status: string; email_logs?: { recipient: string; error?: string }[] };
export type Memory = { id: string; person?: string; time_text?: string; location?: string; topic?: string; summary: string; evidence: string; confidence: number; source_type: string; index_status: string };
export type Meeting = { id: string; file_id: string; filename: string; analyzed_at: string; analysis: { summary: string; topic: string; people: string[]; time?: string; decisions: string[]; action_items: string[] }; tasks: Task[] };
export type Health = { capabilities: Record<string, boolean>; search_provider: 'deepseek' | 'tavily'; models: { chat: string; embedding: string } };

let csrfToken = '';
export function setCsrfToken(value: string) { csrfToken = value; }
export async function authenticatedFetch(path: string, options?: RequestInit): Promise<Response> {
  const headers = new Headers(options?.headers);
  headers.set('X-Cortex-Request', '1');
  if (options?.method && !['GET', 'HEAD'].includes(options.method.toUpperCase()) && csrfToken) headers.set('X-CSRF-Token', csrfToken);
  if (!(options?.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch('/api' + path, { ...options, headers, credentials: 'same-origin', cache: 'no-store' });
  if (response.status === 401 && path !== '/auth/login') {
    csrfToken = '';
    window.dispatchEvent(new Event('cortex:unauthorized'));
  }
  return response;
}
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await authenticatedFetch(path, options);
  if (!response.ok) {
    let message = `请求失败 (${response.status})`;
    try { const data = await response.json(); if (typeof data.detail === 'string') message = data.detail; } catch { /* An offline backend may return HTML. */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
export function safeHref(value: string): string | undefined {
  if (/^https?:\/\//i.test(value) || (value.startsWith('/api/') && !value.includes('\\'))) return value;
}
