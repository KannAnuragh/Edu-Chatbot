export interface User {
  id: string;
  name: string;
  email: string;
  role: "admin" | "student";
  created_at: string;
}

export interface Project {
  id: string;
  title: string;
  description?: string;
  badge_color?: string;
  created_at: string;
  updated_at: string;
  document_count?: number;
}
// Alias for backwards compatibility with reference implementation
export type Course = Project;

export interface Document {
  id: string;
  filename: string;
  file_path?: string;
  file_size: number;
  page_count: number;
  language: string | null;
  status: "pending" | "processing" | "ready" | "failed";
  error_message: string | null;
  created_at: string;
}

export interface SourceReference {
  document_id?: string;
  filename: string;
  page_number: number;
  chunk_text: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceReference[];
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  course_id: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
}

export interface SSEEvent {
  type: "meta" | "token" | "sources" | "done" | "error";
  data: any;
}
