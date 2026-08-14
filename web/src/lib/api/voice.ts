"use client";

/**
 * xnch voice API — proxies to /nexi/voice/* through the same-origin gateway
 * route. STT accepts WAV 16-bit PCM mono; TTS returns WAV.
 */

const BASE = "/api/gateway/nexi/voice";

export interface TranscriptResult {
  transcript: string;
  duration_s: number;
  language: string;
}

export async function transcribeWav(wav: Blob): Promise<TranscriptResult> {
  const form = new FormData();
  form.append("audio", wav, "recording.wav");
  form.append("format", "wav");
  const resp = await fetch(`${BASE}/transcribe`, { method: "POST", body: form });
  return parseJson(resp);
}

export async function speakWav(text: string): Promise<Blob> {
  const resp = await fetch(`${BASE}/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!resp.ok) {
    let detail = `TTS failed (${resp.status})`;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return resp.blob();
}

export async function playText(text: string): Promise<HTMLAudioElement> {
  const blob = await speakWav(text);
  return playBlob(blob);
}

export function playBlob(blob: Blob): HTMLAudioElement {
  stopAudio();
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  activeAudio = audio;
  void audio.play();
  return audio;
}

let activeAudio: HTMLAudioElement | null = null;

export function stopAudio(): void {
  activeAudio?.pause();
  activeAudio = null;
}

async function parseJson<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return resp.json() as Promise<T>;
}
