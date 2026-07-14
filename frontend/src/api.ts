import type { UICommand } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

interface ApiErrorBody {
  error?: { code?: string; message?: string };
}

export class ApiError extends Error {
  code: string | null;

  constructor(message: string, code: string | null) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
  }
}

async function throwApiError(response: Response, fallback: string): Promise<never> {
  let detail = '';
  let code: string | null = null;
  try {
    const body = (await response.json()) as ApiErrorBody;
    detail = body.error?.message ?? '';
    code = body.error?.code ?? null;
  } catch {
    // response body wasn't JSON; fall through with no extra detail
  }
  const message = detail ? `${fallback}: ${detail}` : `${fallback} (status ${response.status})`;
  throw new ApiError(message, code);
}

export interface HealthResponse {
  status: string;
  version: string;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`);
  }
  return response.json();
}

export interface SessionResponse {
  session_id: string;
  learner_id: string | null;
  greeting_audio_b64: string;
  greeting_text: string;
  ui: UICommand;
  stage: string;
}

export async function postSession(
  language?: 'gu-IN' | 'hi-IN' | 'en-IN',
  learnerName?: string,
  pin?: string,
): Promise<SessionResponse> {
  // No language -> the voice-first path: Saathi opens by asking for it.
  const response = await fetch(`${API_BASE_URL}/api/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ language, learner_name: learnerName, pin }),
  });
  if (!response.ok) {
    await throwApiError(response, 'Session start failed');
  }
  return response.json();
}

export interface TurnResponse {
  transcript: string | null;
  reply_text: string;
  reply_audio_b64: string;
  ui: UICommand;
  stage: string;
  latency_ms: { stt: number; agent: number; tts: number };
}

export type TurnInput = { audioBlob: Blob } | { tappedOptionId: string };

export async function postTurn(sessionId: string, input: TurnInput): Promise<TurnResponse> {
  const formData = new FormData();
  formData.append('session_id', sessionId);
  if ('audioBlob' in input) {
    formData.append('audio', input.audioBlob, 'clip.webm');
  } else {
    formData.append('tapped_option_id', input.tappedOptionId);
  }

  const response = await fetch(`${API_BASE_URL}/api/turn`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    await throwApiError(response, 'Turn request failed');
  }
  return response.json();
}
