"use client";

/**
 * Browser microphone -> 16kHz mono 16-bit PCM WAV.
 *
 * The xnch voice backend accepts ONLY WAV 16-bit PCM mono (or raw PCM), so we
 * capture via the Web Audio API and encode the WAV header client-side instead
 * of using MediaRecorder (which produces webm/opus).
 */

const TARGET_SAMPLE_RATE = 16_000;

export interface VoiceRecorderOptions {
  /** Auto-stop after this many ms (default 55s — backend caps at 60s). */
  maxDurationMs?: number;
  /** Called ~every frame with the current RMS level (0..1) for the UI. */
  onLevel?: (rms: number) => void;
  /** Called when the max duration is hit; the caller should stop+transcribe. */
  onTimeout?: () => void;
}

function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const write = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) {
      view.setUint8(offset + i, text.charCodeAt(i));
    }
  };
  write(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true); // fmt chunk size
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  write(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function downsample(input: Float32Array, from: number, to: number): Float32Array {
  if (from === to) return input;
  const ratio = from / to;
  const outLen = Math.floor(input.length / ratio);
  const out = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const src = i * ratio;
    const i0 = Math.floor(src);
    const i1 = Math.min(i0 + 1, input.length - 1);
    const frac = src - i0;
    out[i] = input[i0] * (1 - frac) + input[i1] * frac;
  }
  return out;
}

export class VoiceRecorder {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private processor: ScriptProcessorNode | null = null;
  private chunks: Float32Array[] = [];
  private totalSamples = 0;
  private startedAt = 0;
  private timeoutId: number | null = null;
  private readonly maxDurationMs: number;
  private readonly onLevel?: (rms: number) => void;
  private readonly onTimeout?: () => void;

  constructor(opts: VoiceRecorderOptions = {}) {
    this.maxDurationMs = opts.maxDurationMs ?? 55_000;
    this.onLevel = opts.onLevel;
    this.onTimeout = opts.onTimeout;
  }

  get durationMs(): number {
    return this.startedAt ? Date.now() - this.startedAt : 0;
  }

  get isRecording(): boolean {
    return this.stream !== null;
  }

  async start(): Promise<void> {
    if (this.stream) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Microphone capture is not available in this browser");
    }
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    const ctx = new AudioContext();
    await ctx.resume();
    this.ctx = ctx;
    this.source = ctx.createMediaStreamSource(this.stream);
    this.processor = ctx.createScriptProcessor(4096, 1, 1);
    this.processor.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      this.chunks.push(new Float32Array(input));
      this.totalSamples += input.length;
      if (this.onLevel) {
        let sum = 0;
        for (let i = 0; i < input.length; i++) sum += input[i] * input[i];
        this.onLevel(Math.sqrt(sum / input.length));
      }
    };
    this.source.connect(this.processor);
    this.processor.connect(ctx.destination);
    this.startedAt = Date.now();
    this.timeoutId = window.setTimeout(() => {
      this.onTimeout?.();
    }, this.maxDurationMs);
  }

  /** Stop recording and return the captured audio as a WAV blob. */
  async stop(): Promise<Blob> {
    const ctxRate = this.ctx?.sampleRate ?? TARGET_SAMPLE_RATE;
    const buffer = new Float32Array(this.totalSamples);
    let offset = 0;
    for (const chunk of this.chunks) {
      buffer.set(chunk, offset);
      offset += chunk.length;
    }
    this.cleanup();
    if (buffer.length === 0) {
      throw new Error("No audio captured");
    }
    const pcm = downsample(buffer, ctxRate, TARGET_SAMPLE_RATE);
    return encodeWav(pcm, TARGET_SAMPLE_RATE);
  }

  /** Abort without producing audio (e.g. user released a mis-tap). */
  cancel(): void {
    this.cleanup();
    this.chunks = [];
    this.totalSamples = 0;
  }

  private cleanup(): void {
    if (this.timeoutId != null) window.clearTimeout(this.timeoutId);
    this.timeoutId = null;
    this.processor?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    void this.ctx?.close();
    this.processor = null;
    this.source = null;
    this.stream = null;
    this.ctx = null;
  }
}
