export interface Session {
  id: string;
  source: string;
  title: string | null;
  model: string | null;
  started_at: number;
  ended_at: number | null;
  message_count?: number;
  tool_call_count?: number;
}

export interface ToolCall {
  id?: string;
  name?: string;
  type?: string;
  function?: {
    name: string;
    arguments: string;
  };
}

export interface Message {
  id: number;
  session_id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string | null;
  tool_name?: string | null;
  tool_calls?: ToolCall[] | string | null;
  reasoning_content?: string | null;
  timestamp: number;
  active?: number;
}

export interface ShareMetadata {
  token: string;
  allow_live: boolean;
  show_reasoning: boolean;
  created_at: number;
  expires_at: number | null;
  view_count?: number;
}

export interface InitialData {
  session: Session;
  messages: Message[];
  share: ShareMetadata;
}
