let earconEl: HTMLAudioElement | null = null;

function getEarcon(): HTMLAudioElement {
  if (!earconEl) {
    earconEl = new Audio('/earcon.mp3');
    earconEl.preload = 'auto';
  }
  return earconEl;
}

export function playEarcon(): void {
  const el = getEarcon();
  el.currentTime = 0;
  void el.play().catch(() => {
    // Autoplay can be blocked before the first user gesture; safe to ignore.
  });
}

export function playBase64Mp3(base64: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const audio = new Audio(`data:audio/mp3;base64,${base64}`);
    audio.onended = () => resolve();
    audio.onerror = () => reject(new Error('Reply audio playback failed.'));
    audio.play().catch(reject);
  });
}
