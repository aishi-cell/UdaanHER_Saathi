import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { MicOff } from 'lucide-react';
import { ApiError, getHealth, postSession, postTurn, type TurnResponse } from './api';
import { MicPermissionDeniedError, PushToTalkRecorder } from './audio/recorder';
import { playBase64Mp3, playEarcon, unlockAudio } from './audio/player';
import { SpeechWatcher } from './audio/vad';
import { AuroraBackground } from './components/AuroraBackground';
import { Landing } from './components/Landing';
import { Renderer } from './components/Renderer';
import { SaathiAvatar } from './components/SaathiAvatar';
import { TalkButton, type TalkState } from './components/TalkButton';
import { UiDemo } from './UiDemo';
import { cn } from '@/lib/utils';
import type { UICommand } from './types';

const STATUS_LABELS: Record<TalkState, string> = {
  ready: 'माइक दबाइए · Tap to speak',
  listening: 'सुन रही हूँ… बोलिए',
  thinking: 'सोच रही हूँ…',
  speaking: 'Saathi बोल रही हैं…',
};

// A very short clip produces a WebM too short for Sarvam's parser -- pad to
// this floor before stopping so the container is always well-formed.
const MIN_RECORDING_MS = 700;

function friendlyErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.code === 'stt_failed') {
      return "I couldn't hear that clearly -- please try speaking again.";
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
  const [view, setView] = useState<'landing' | 'session'>('landing');
  const [connecting, setConnecting] = useState(false);
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [talkState, setTalkState] = useState<TalkState>('ready');
  const [micDenied, setMicDenied] = useState(false);
  const [lastTurn, setLastTurn] = useState<TurnResponse | null>(null);
  const [currentUi, setCurrentUi] = useState<UICommand>(IDLE_UI);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [sessionReady, setSessionReady] = useState(false);

  const recorderRef = useRef<PushToTalkRecorder>(new PushToTalkRecorder());
  const watcherRef = useRef<SpeechWatcher | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const greetingAudioRef = useRef<string | null>(null);
  const busyRef = useRef(false); // a turn is in flight; don't start listening

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
    if (!errorMessage) return;
    const timeout = setTimeout(() => setErrorMessage(null), 6000);
    return () => clearTimeout(timeout);
  }, [errorMessage]);

  // User-gesture-triggered (the hero button), so no StrictMode double-run to
  // guard against, and the tap unlocks the AudioContext for the greeting.
  // No language is sent: the session opens with Saathi asking for it by
  // voice (choose_language stage), with tappable language cards on screen.
  async function beginSession() {
    if (connecting) return;
    setConnecting(true);
    void unlockAudio();
    setView('session');
    try {
      const result = await postSession();
      sessionIdRef.current = result.session_id;
      setCurrentUi(result.ui);
      setSessionReady(true);
      setTalkState('speaking');
      try {
        await playBase64Mp3(result.greeting_audio_b64);
      } catch (err) {
        console.error('[talk] greeting autoplay failed:', err);
        greetingAudioRef.current = result.greeting_audio_b64;
      }
      setTalkState('ready');
      void startListening(); // continuous mode: her turn begins right away
    } catch (err) {
      console.error('[talk] could not start session:', err);
      setErrorMessage(
        err instanceof Error ? err.message : 'Could not reach the mentor. Try reloading.',
      );
      setConnecting(false);
      setView('landing');
    }
  }

  /** Start hands-free listening: record + watch for her to finish speaking.
   * Resolves silently if the mic can't start or a turn is already busy. */
  async function startListening() {
    if (busyRef.current || recorderRef.current.isRecording || !sessionIdRef.current) return;
    if (greetingAudioRef.current) {
      const greeting = greetingAudioRef.current;
      greetingAudioRef.current = null;
      void playBase64Mp3(greeting).catch((err) => console.error('[talk] greeting failed:', err));
    }
    try {
      await recorderRef.current.start();
    } catch (err) {
      console.error('[talk] could not start recording:', err);
      if (err instanceof MicPermissionDeniedError) setMicDenied(true);
      else setErrorMessage(friendlyErrorMessage(err));
      return;
    }
    setTalkState('listening');
    const stream = recorderRef.current.mediaStream;
    if (!stream) return;
    watcherRef.current?.stop();
    watcherRef.current = new SpeechWatcher(stream, {
      onUtteranceEnd: () => void sendListenedTurn(),
      // She stayed quiet: stop listening, wait for a tap. Never an error --
      // silence is a normal thing to do.
      onNoSpeech: () => void discardListening(),
    });
    watcherRef.current.start();
  }

  async function stopRecorder(): Promise<Blob | null> {
    watcherRef.current?.stop();
    watcherRef.current = null;
    if (!recorderRef.current.isRecording) return null;
    try {
      return await recorderRef.current.stop();
    } catch (err) {
      console.error('[talk] could not stop recording:', err);
      return null;
    }
  }

  async function discardListening() {
    await stopRecorder();
    setTalkState('ready');
  }

  async function sendListenedTurn() {
    // Pad very short utterances so the WebM container is parseable.
    await new Promise((resolve) => setTimeout(resolve, MIN_RECORDING_MS / 2));
    const audioBlob = await stopRecorder();
    if (!audioBlob || audioBlob.size === 0) {
      setTalkState('ready');
      return;
    }
    await runTurn({ audioBlob });
  }

  async function runTurn(input: Parameters<typeof postTurn>[1]) {
    const sessionId = sessionIdRef.current;
    if (!sessionId) {
      setErrorMessage('Still connecting to the mentor -- try again in a moment.');
      return;
    }
    busyRef.current = true;
    setTalkState('thinking');
    playEarcon();
    try {
      const result = await postTurn(sessionId, input);
      setLastTurn(result);
      setCurrentUi(result.ui);
      setTalkState('speaking');
      await playBase64Mp3(result.reply_audio_b64);
      busyRef.current = false;
      setTalkState('ready');
      void startListening(); // continuous conversation: back to her
    } catch (err) {
      console.error('[talk] turn failed:', err);
      setErrorMessage(friendlyErrorMessage(err));
      busyRef.current = false;
      setTalkState('ready'); // no auto-listen after an error; she taps
    }
  }

  /** The big button: tap while listening sends the turn now; tap while
   * ready starts listening (e.g. after a quiet timeout). */
  async function handleTap() {
    void unlockAudio();
    if (talkState === 'listening') {
      await sendListenedTurn();
      return;
    }
    if (talkState === 'ready' && sessionReady) {
      await startListening();
    }
  }

  async function handleTapOption(optionId: string) {
    if (busyRef.current) return;
    if (talkState === 'listening') await discardListening();
    await runTurn({ tappedOptionId: optionId });
  }

  async function handlePhoto(file: File) {
    if (busyRef.current) return;
    if (talkState === 'listening') await discardListening();
    await runTurn({ photoBlob: file });
  }

  if (isUiDemo) {
    return <UiDemo />;
  }

  if (micDenied) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-6 px-8 text-center">
        <AuroraBackground />
        <div className="flex size-20 items-center justify-center rounded-full bg-destructive/10 text-destructive">
          <MicOff className="size-10" />
        </div>
        <p className="max-w-md text-xl font-medium">
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
    <div className="relative flex h-full flex-col overflow-hidden">
      <AuroraBackground />

      {/* backend status dot */}
      <span
        className={cn(
          'absolute right-4 top-4 z-20 size-3 rounded-full transition-colors',
          backendUp ? 'bg-emerald-500' : 'bg-red-500',
          backendUp && 'shadow-[0_0_8px_2px_rgb(16_185_129/0.5)]',
        )}
        aria-label={backendUp ? 'Backend connected' : 'Backend unreachable'}
      />

      <AnimatePresence mode="wait">
        {view === 'landing' ? (
          <motion.div
            key="landing"
            className="h-full"
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.35 }}
          >
            <Landing connecting={connecting} onStart={beginSession} />
          </motion.div>
        ) : (
          <motion.div
            key="session"
            className="flex h-full flex-col"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4 }}
          >
            <header className="flex items-center justify-center pt-5">
              <span className="text-lg font-bold tracking-tight text-brand-800">
                Udaan <span className="text-blush-600">Her Saathi</span>
              </span>
            </header>

            <main className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto p-4 sm:p-6">
              <AnimatePresence mode="wait">
                <motion.div
                  key={currentUi.type}
                  className="flex w-full justify-center"
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  transition={{ duration: 0.3 }}
                >
                  {currentUi.type === 'idle' ? (
                    <SaathiAvatar
                      talking={talkState === 'speaking' || talkState === 'listening'}
                      aria-label="Saathi, your mentor"
                    />
                  ) : (
                    <Renderer ui={currentUi} onTapOption={handleTapOption} onPhoto={handlePhoto} />
                  )}
                </motion.div>
              </AnimatePresence>
            </main>

            <footer className="flex flex-col items-center gap-4 pb-8 pt-2">
              <AnimatePresence mode="wait">
                <motion.p
                  key={sessionReady ? talkState : 'connecting'}
                  className={cn(
                    'rounded-full px-5 py-1.5 text-lg font-medium text-brand-800',
                    talkState === 'listening' ? 'bg-brand-100 shadow-sm' : 'bg-transparent',
                  )}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.18 }}
                >
                  {sessionReady ? STATUS_LABELS[talkState] : 'Saathi आ रही हैं…'}
                </motion.p>
              </AnimatePresence>
              <TalkButton state={talkState} disabled={!sessionReady} onTap={handleTap} />
            </footer>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {errorMessage && (
          <motion.div
            role="alert"
            className="fixed inset-x-4 bottom-6 z-30 mx-auto max-w-md rounded-2xl bg-foreground/90 px-6 py-4 text-center text-base font-medium text-white shadow-2xl backdrop-blur"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 24 }}
          >
            {errorMessage}
          </motion.div>
        )}
      </AnimatePresence>

      {isDebug && lastTurn && (
        <div className="fixed bottom-2 left-2 z-30 rounded-lg bg-black/70 px-3 py-2 font-mono text-xs text-white">
          <div>transcript: {lastTurn.transcript ?? '(none)'}</div>
          <div>latency sum: {latencySum}ms</div>
        </div>
      )}
    </div>
  );
}

export default App;
