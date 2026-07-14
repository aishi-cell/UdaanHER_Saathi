const PREFERRED_MIME_TYPE = 'audio/webm;codecs=opus';

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined;
  if (MediaRecorder.isTypeSupported(PREFERRED_MIME_TYPE)) return PREFERRED_MIME_TYPE;
  return undefined;
}

export class MicPermissionDeniedError extends Error {
  constructor() {
    super('Microphone permission was denied.');
    this.name = 'MicPermissionDeniedError';
  }
}

export class PushToTalkRecorder {
  private stream: MediaStream | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private chunks: BlobPart[] = [];
  private mimeType = PREFERRED_MIME_TYPE;

  get isRecording(): boolean {
    return this.mediaRecorder?.state === 'recording';
  }

  /** The live mic stream while recording -- the speech watcher taps it. */
  get mediaStream(): MediaStream | null {
    return this.stream;
  }

  async start(): Promise<void> {
    if (this.isRecording) return;

    if (!this.stream) {
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch {
        throw new MicPermissionDeniedError();
      }
    }

    this.chunks = [];
    const mimeType = pickMimeType();
    this.mimeType = mimeType ?? PREFERRED_MIME_TYPE;
    this.mediaRecorder = mimeType
      ? new MediaRecorder(this.stream, { mimeType })
      : new MediaRecorder(this.stream);
    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) this.chunks.push(event.data);
    };
    this.mediaRecorder.start();
  }

  stop(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      const recorder = this.mediaRecorder;
      if (!recorder || recorder.state !== 'recording') {
        reject(new Error('Recorder is not currently recording.'));
        return;
      }
      recorder.onstop = () => {
        resolve(new Blob(this.chunks, { type: this.mimeType }));
      };
      recorder.stop();
    });
  }
}
