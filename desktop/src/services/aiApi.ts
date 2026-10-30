import { apiGet, apiPost } from "./api";


export type AIProvider =
  | "auto"
  | "gpt"
  | "gemini"
  | "llama"
  | "deepseek"
  | "mock";

export type AITask =
  | "analyze_repository"
  | "generate_tests"
  | "generate_automation"
  | "analyze_failure"
  | "self_heal"
  | "explain_code";

export interface AIChatRequest {
  task: AITask;
  prompt: string;
  provider?: AIProvider;
  fallback_providers?: string[];
  repository_path?: string | null;
  context?: string | null;
  temperature?: number;
  max_tokens?: number;
}

export interface AIChatResponse {
  task: AITask;
  provider: string;
  model: string;
  content: string;
  input_tokens?: number | null;
  output_tokens?: number | null;
}

export interface ProviderStatus {
  provider: string;
  model: string;
  available: boolean;
}

export async function sendAIChat(
  request: AIChatRequest,
): Promise<AIChatResponse> {
  return apiPost<AIChatResponse>(
    "/agents/execute",
    request,
  );
}

export async function getAIProviderStatus(): Promise<
  ProviderStatus[]
> {
  return apiGet<ProviderStatus[]>(
    "/providers/status",
  );
}