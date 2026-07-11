import { useEffect, useRef, useState } from 'react';
import { getHealth, postTurn, type TurnResponse } from './api';
import { MicPermissionDeniedError, PushToTalkRecorder } from './audio/recorder';
import { playBase64Mp3, playEarcon } from './audio/player';
import './App.css';

type TalkState = 'ready' | 'listening' | 'thinking' | 'speaking';

const STATUS_LABELS: Record<TalkState, string> = {
  ready: 'ready',
  listening: 'listening...',
  thinking: 'thinking...',
  speaking: 'speaking...',
};

const isDebug = new URLSearchParams(window.location.search).get('debug') === '1';

function App() {
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [talkState, setTalkState] = useState<TalkState>('ready');
  const [micDenied, setMicDenied] = useState(false);
  const [lastTurn, setLastTurn] = useState<TurnResponse | null>(null);

  const recorderRef = useRef<PushToTalkRecorder>(new PushToTalkRecorder());
  const sessionIdRef = useRef<string>(crypto.randomUUID());

  useEffect(() => {
    let cancelled = false;

    async function checkHealth() {
      try {
        await getHealth();
        if (!cancelled) setBackendUp(true);
      } catch {
        if (!cancelled) setBackendUp(false);
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  async function handlePressStart() {
    if (talkState !== 'ready' || recorderRef.current.isRecording) return;
    try {
      await recorderRef.current.start();
      setTalkState('listening');
    } catch (err) {
      if (err instanceof MicPermissionDeniedError) {
        setMicDenied(true);
      }
    }
  }

  async function handlePressEnd() {
    if (!recorderRef.current.isRecording) return;
    setTalkState('thinking');
    playEarcon();

    try {
      const audioBlob = await recorderRef.current.stop();
      const result = await postTurn(sessionIdRef.current, audioBlob);
      setLastTurn(result);
      setTalkState('speaking');
      await playBase64Mp3(result.reply_audio_b64);
    } catch (err) {
      console.error('Turn failed:', err);
    } finally {
      setTalkState('ready');
    }
  }

  if (micDenied) {
    return (
      <div className="kiosk mic-denied">
        <p>
          We need microphone access to talk with you. Please allow the microphone permission for
          this site in your browser settings, then reload the page.
        </p>
      </div>
    );
  }

  const latencySum = lastTurn
    ? lastTurn.latency_ms.stt + lastTurn.latency_ms.agent + lastTurn.latency_ms.tts
    : null;

  return (
    <div className="kiosk">
      <span
        className={`status-dot ${backendUp ? 'status-dot--up' : 'status-dot--down'}`}
        aria-label={backendUp ? 'Backend connected' : 'Backend unreachable'}
      />

      <section className="content-area">
        <div className="placeholder-illustration" role="img" aria-label="Mentor waiting to talk">
          🌼
        </div>
      </section>

      <section className="talk-area">
        <p className="status-line">{STATUS_LABELS[talkState]}</p>
        <button
          type="button"
          className={`talk-button talk-button--${talkState}`}
          aria-label="Hold to talk"
          onPointerDown={handlePressStart}
          onPointerUp={handlePressEnd}
          onPointerLeave={handlePressEnd}
        >
          {talkState === 'thinking' ? <span className="spinner" /> : '🎤'}
        </button>
      </section>

      {isDebug && lastTurn && (
        <div className="debug-panel">
          <div>transcript: {lastTurn.transcript ?? '(none)'}</div>
          <div>latency sum: {latencySum}ms</div>
        </div>
      )}
    </div>
  );
}

export default App;
