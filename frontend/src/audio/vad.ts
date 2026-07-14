/** Speech-end detection for continuous conversation: watches the mic
 * stream's loudness and reports when she has spoken and then gone quiet
 * (turn over), or never spoke at all (stop listening, save the mic). */

export interface SpeechWatcherCallbacks {
  /** She spoke, then stayed quiet for silenceMs -- send the turn. */
  onUtteranceEnd: () => void;
  /** Nothing said within noSpeechMs -- stop listening quietly. */
  onNoSpeech: () => void;
}

const SILENCE_MS = 1400;
const NO_SPEECH_MS = 8000;
const MAX_UTTERANCE_MS = 20000; // hard cap: send whatever we have
const RMS_SPEECH_THRESHOLD = 0.02;
const TICK_MS = 50;

export class SpeechWatcher {
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private buffer: Float32Array = new Float32Array(0);
  private startedAt = 0;
  private speechStartedAt = 0;
  private lastLoudAt = 0;
  private done = false;

  private stream: MediaStream;
  private callbacks: SpeechWatcherCallbacks;

  constructor(stream: MediaStream, callbacks: SpeechWatcherCallbacks) {
    this.stream = stream;
    this.callbacks = callbacks;
  }

  start(): void {
    this.ctx = new AudioContext();
    const source = this.ctx.createMediaStreamSource(this.stream);
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 1024;
    source.connect(this.analyser);
    this.buffer = new Float32Array(this.analyser.fftSize);
    this.startedAt = Date.now();
    this.timer = setInterval(() => this.tick(), TICK_MS);
  }

  stop(): void {
    this.done = true;
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    void this.ctx?.close().catch(() => undefined);
    this.ctx = null;
  }

  private tick(): void {
    if (this.done || !this.analyser) return;
    this.analyser.getFloatTimeDomainData(this.buffer as Float32Array<ArrayBuffer>);
    let sum = 0;
    for (let i = 0; i < this.buffer.length; i++) sum += this.buffer[i] * this.buffer[i];
    const rms = Math.sqrt(sum / this.buffer.length);
    const now = Date.now();

    if (rms >= RMS_SPEECH_THRESHOLD) {
      if (!this.speechStartedAt) this.speechStartedAt = now;
      this.lastLoudAt = now;
    }

    if (!this.speechStartedAt) {
      if (now - this.startedAt >= NO_SPEECH_MS) this.finish(this.callbacks.onNoSpeech);
      return;
    }
    if (now - this.lastLoudAt >= SILENCE_MS || now - this.speechStartedAt >= MAX_UTTERANCE_MS) {
      this.finish(this.callbacks.onUtteranceEnd);
    }
  }

  private finish(callback: () => void): void {
    if (this.done) return;
    this.stop();
    callback();
  }
}
