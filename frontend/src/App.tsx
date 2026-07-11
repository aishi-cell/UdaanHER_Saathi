import { useEffect, useRef, useState } from 'react';
import { ApiError, getHealth, postSession, postTurn, type TurnResponse } from './api';
import { MicPermissionDeniedError, PushToTalkRecorder } from './audio/recorder';
import { playBase64Mp3, playEarcon, unlockAudio } from './audio/player';
import { Renderer } from './components/Renderer';
import { UiDemo } from './UiDemo';
import type { UICommand } from './types';
import './App.css';

type TalkState = 'ready' | 'listening' | 'thinking' | 'speaking';

const STATUS_LABELS: Record<TalkState, string> = {
  ready: 'ready',
  listening: 'listening...',
  thinking: 'thinking...',
  speaking: 'speaking...',
};

// A very short hold (an accidental tap, or someone testing the button)
// produces a WebM clip too short for Sarvam's parser -- "Failed to read the
// file, please check the audio format". Padding out to this floor before
// actually stopping avoids that failure mode entirely; it's not about
// capturing more of what she said, just giving the recorder enough time to
// produce a well-formed container.
const MIN_RECORDING_MS = 700;

function friendlyErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === 'stt_failed') {
      return "I couldn't hear that clearly -- please hold the button a little longer and try again.";
    }
    if (err.code === 'tts_failed') {
      return 'I had trouble speaking just now -- please try again.';
    }
  }
  return err instanceof Error ? err.message : 'Something went wrong. Try again.';
}

const searchParams = new URLSearchParams(window.location.search);
const isDebug = searchParams.get('debug') === '1';
const isUiDemo = searchParams.get('ui-demo') === '1';

const IDLE_UI: UICommand = { type: 'idle' };

function App() {
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [talkState, setTalkState] = useState<TalkState>('ready');
  const [micDenied, setMicDenied] = useState(false);
  const [lastTurn, setLastTurn] = useState<TurnResponse | null>(null);
  const [currentUi, setCurrentUi] = useState<UICommand>(IDLE_UI);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [sessionReady, setSessionReady] = useState(false);

  const recorderRef = useRef<PushToTalkRecorder>(new PushToTalkRecorder());
  const sessionIdRef = useRef<string | null>(null);
  const greetingAudioRef = useRef<string | null>(null);
  const releaseRequestedRef = useRef(false);
  const startingRef = useRef(false);
  const sessionStartedRef = useRef(false);
  const recordingStartedAtRef = useRef(0);

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

  useEffect(() => {
    // Guarded by a ref (not a `cancelled` closure flag) because
    // React StrictMode's dev-only mount->cleanup->mount cycle would
    // otherwise poison the one real call's `cancelled` flag via the first
    // cleanup, discarding its result even though the ref guard ensures it's
    // the only call that ever actually runs.
    if (sessionStartedRef.current) return;
    sessionStartedRef.current = true;

    async function startSession() {
      try {
        // No language picker yet (T13) -- default to Hindi for now.
        const result = await postSession('hi-IN');
        sessionIdRef.current = result.session_id;
        greetingAudioRef.current = result.greeting_audio_b64;
        setCurrentUi(result.ui);
        setSessionReady(true);
      } catch (err) {
        console.error('[talk] could not start session:', err);
        setErrorMessage(
          err instanceof Error ? err.message : 'Could not reach the mentor. Try reloading.',
        );
      }
    }

    void startSession();
  }, []);

  useEffect(() => {
    if (!errorMessage) return;
    const timeout = setTimeout(() => setErrorMessage(null), 6000);
    return () => clearTimeout(timeout);
  }, [errorMessage]);

  async function handlePressStart() {
    console.log('[talk] pressStart', { talkState, isRecording: recorderRef.current.isRecording });
    if (
      talkState !== 'ready' ||
      !sessionReady ||
      recorderRef.current.isRecording ||
      startingRef.current
    )
      return;
    startingRef.current = true;
    releaseRequestedRef.current = false;
    void unlockAudio();
    if (greetingAudioRef.current) {
      const greeting = greetingAudioRef.current;
      greetingAudioRef.current = null;
      void playBase64Mp3(greeting).catch((err) => console.error('[talk] greeting failed:', err));
    }
    try {
      // getUserMedia is async and can take a noticeable moment (mic
      // permission prompt, device init). A fast tap can release the button
      // before this resolves -- track that so we don't get stuck "listening"
      // forever with nothing to ever call stop().
      await recorderRef.current.start();
      recordingStartedAtRef.current = Date.now();
      console.log('[talk] recorder started', { releaseRequested: releaseRequestedRef.current });
      startingRef.current = false;
      if (releaseRequestedRef.current) {
        await finishTurn();
      } else {
        setTalkState('listening');
      }
    } catch (err) {
      startingRef.current = false;
      console.error('[talk] could not start recording:', err);
      if (err instanceof MicPermissionDeniedError) {
        setMicDenied(true);
      } else {
        setErrorMessage(friendlyErrorMessage(err));
      }
    }
  }

  async function runTurn(input: Parameters<typeof postTurn>[1]) {
    console.log('[talk] runTurn', input);
    const sessionId = sessionIdRef.current;
    if (!sessionId) {
      setErrorMessage('Still connecting to the mentor -- try again in a moment.');
      return;
    }
    setTalkState('thinking');
    playEarcon();
    try {
      const result = await postTurn(sessionId, input);
      console.log('[talk] turn succeeded', result);
      setLastTurn(result);
      setCurrentUi(result.ui);
      setTalkState('speaking');
      await playBase64Mp3(result.reply_audio_b64);
      console.log('[talk] playback finished');
    } catch (err) {
      console.error('[talk] turn failed:', err);
      setErrorMessage(friendlyErrorMessage(err));
    } finally {
      setTalkState('ready');
    }
  }

  async function finishTurn() {
    try {
      const elapsed = Date.now() - recordingStartedAtRef.current;
      console.log('[talk] finishTurn elapsed since start:', elapsed, 'ms');
      if (elapsed < MIN_RECORDING_MS) {
        console.log('[talk] padding to', MIN_RECORDING_MS, 'ms');
        await new Promise((resolve) => setTimeout(resolve, MIN_RECORDING_MS - elapsed));
      }
      const audioBlob = await recorderRef.current.stop();
      console.log('[talk] audioBlob size:', audioBlob.size, 'type:', audioBlob.type);
      await runTurn({ audioBlob });
    } catch (err) {
      console.error('Could not stop recording:', err);
      setErrorMessage(friendlyErrorMessage(err));
      setTalkState('ready');
    }
  }

  async function handlePressEnd() {
    console.log('[talk] pressEnd', {
      starting: startingRef.current,
      isRecording: recorderRef.current.isRecording,
    });
    if (startingRef.current) {
      // Still waiting on getUserMedia; handlePressStart will finish the
      // turn itself as soon as it resolves.
      releaseRequestedRef.current = true;
      return;
    }
    if (!recorderRef.current.isRecording) return;
    await finishTurn();
  }

  async function handleTapOption(optionId: string) {
    if (talkState !== 'ready') return;
    await runTurn({ tappedOptionId: optionId });
  }

  if (isUiDemo) {
    return <UiDemo />;
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
        {currentUi.type === 'idle' ? (
          <div className="idle-hero">
            <div className="idle-hero__glow" />
            <div
              className="placeholder-illustration"
              role="img"
              aria-label="Mentor waiting to talk"
            >
              🌸
            </div>
          </div>
        ) : (
          <Renderer ui={currentUi} onTapOption={handleTapOption} />
        )}
      </section>

      <section className="talk-area">
        <p className="status-line">{sessionReady ? STATUS_LABELS[talkState] : 'connecting...'}</p>
        <button
          type="button"
          className={`talk-button talk-button--${talkState}`}
          aria-label="Hold to talk"
          onPointerDown={handlePressStart}
          onPointerUp={handlePressEnd}
          onPointerLeave={handlePressEnd}
        >
          {talkState === 'thinking' && <span className="spinner" />}
          {talkState === 'speaking' && (
            <span className="waveform" aria-hidden="true">
              <span />
              <span />
              <span />
              <span />
              <span />
            </span>
          )}
          {(talkState === 'ready' || talkState === 'listening') && '🎤'}
        </button>
      </section>

      {errorMessage && (
        <div className="error-toast" role="alert">
          {errorMessage}
        </div>
      )}

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
