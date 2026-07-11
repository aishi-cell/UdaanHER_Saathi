let audioContext: AudioContext | null = null;
let earconBuffer: AudioBuffer | null = null;

function getAudioContext(): AudioContext {
  if (!audioContext) {
    audioContext = new AudioContext();
  }
  return audioContext;
}

/**
 * Must be called synchronously from within a user gesture (e.g. the very
 * start of a pointerdown handler). Turn round trips (STT+agent+TTS) commonly
 * take several seconds -- long enough that a browser's autoplay policy can
 * reject a fresh `new Audio().play()` call made after that delay, since
 * transient user-activation has expired by the time the reply audio is
 * ready. Resuming a Web Audio AudioContext during the gesture keeps it
 * unlocked for the rest of the session, so later playback doesn't need its
 * own fresh gesture.
 */
export async function unlockAudio(): Promise<void> {
  const ctx = getAudioContext();
  if (ctx.state === 'suspended') {
    await ctx.resume();
  }
  if (!earconBuffer) {
    try {
      const response = await fetch('/earcon.mp3');
      const arrayBuffer = await response.arrayBuffer();
      earconBuffer = await ctx.decodeAudioData(arrayBuffer);
    } catch {
      // Earcon is a nice-to-have; a load failure shouldn't block anything.
    }
  }
}

export function playEarcon(): void {
  if (!earconBuffer) return;
  const ctx = getAudioContext();
  const source = ctx.createBufferSource();
  source.buffer = earconBuffer;
  source.connect(ctx.destination);
  source.start();
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

export async function playBase64Mp3(base64: string): Promise<void> {
  const ctx = getAudioContext();
  if (ctx.state === 'suspended') {
    await ctx.resume();
  }
  const audioBuffer = await ctx.decodeAudioData(base64ToArrayBuffer(base64));

  return new Promise((resolve, reject) => {
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    source.onended = () => resolve();
    try {
      source.start();
    } catch (err) {
      reject(err instanceof Error ? err : new Error('Reply audio playback failed.'));
    }
  });
}
