const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

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

export interface TurnResponse {
  transcript: string | null;
  reply_text: string;
  reply_audio_b64: string;
  ui: { type: string };
  stage: string;
  latency_ms: { stt: number; agent: number; tts: number };
}

export async function postTurn(sessionId: string, audioBlob: Blob): Promise<TurnResponse> {
  const formData = new FormData();
  formData.append('session_id', sessionId);
  formData.append('audio', audioBlob, 'clip.webm');

  const response = await fetch(`${API_BASE_URL}/api/turn`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) {
    throw new Error(`Turn request failed with status ${response.status}`);
  }
  return response.json();
}
