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

export interface CheatSheetSection {
  title: string;
  items: string[];
}

export interface CheatSheet {
  id: string;
  title: string;
  summary: string;
  sections: CheatSheetSection[];
  generated_at: string;
  raw_markdown?: string;
}

export type ExplainMode = "ELI5" | "DEEP_DIVE" | "EXAM_FOCUSED";

export interface ExplainPromptPayload {
  modes: ExplainMode[];
}

export interface ExplainResponse {
  mode: ExplainMode;
  concept: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceReference[];
  created_at: string;
  cheatSheet?: CheatSheet;
  explain?: {
    variant: "prompt" | "response";
    data: ExplainPromptPayload | ExplainResponse;
  };
  // Optional structured quiz payload. When present, the message bubble
  // renders a QuizCard alongside its text content. This is the in-memory
  // representation of the structured quiz state that the backend persists
  // on Conversation.quiz_state.
  quiz?: {
    variant: "topics" | "question" | "result" | "complete";
    data: QuizTopicsPayload | QuizQuestion | QuizResult;
  };
}

export interface Conversation {
  id: string;
  title: string;
  course_id: string;
  quiz_state?: {
    language: "ENGLISH" | "MALAYALAM";
    topic: string | null;
    topics: string[];
    questions: QuizQuestion[];
    current_index: number;
    score: number;
    completed: boolean;
    history: Array<{ index: number; question_id: string; selected: string; correct: boolean }>;
  } | null;
  created_at: string;
  updated_at: string;
  messages: Message[];
}

export interface SSEEvent {
  type:
    | "meta"
    | "token"
    | "sources"
    | "done"
    | "error"
    | "status"
    | "quiz_topics"
    | "cheat_sheet"
    | "explain_prompt"
    | "quiz_question"
    | "quiz_result";
  data: any;
}

export interface QuizOption {
  key: "A" | "B" | "C" | "D";
  text: string;
}

export interface QuizQuestion {
  id: string;
  topic: string;
  stem: string;
  options: QuizOption[];
  index: number;
  total: number;
}

export interface QuizResult {
  is_correct: boolean;
  correct_key: "A" | "B" | "C" | "D";
  explanation: string;
  score: number;
  total: number;
  finished: boolean;
}

export interface QuizTopicsPayload {
  language: "ENGLISH" | "MALAYALAM";
  topics: string[];
}
