import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { MicOff } from 'lucide-react';
import { ApiError, getHealth, postSession, postTurn, type TurnResponse } from './api';
import { MicPermissionDeniedError, PushToTalkRecorder } from './audio/recorder';
import { playBase64Mp3, playEarcon, unlockAudio } from './audio/player';
import { AuroraBackground } from './components/AuroraBackground';
import { Landing, type Language } from './components/Landing';
import { Renderer } from './components/Renderer';
import { SaathiAvatar } from './components/SaathiAvatar';
import { TalkButton, type TalkState } from './components/TalkButton';
import { UiDemo } from './UiDemo';
import { cn } from '@/lib/utils';
import type { UICommand } from './types';

const STATUS_LABELS: Record<TalkState, string> = {
  ready: 'दबाकर बोलिए · Hold & speak',
  listening: 'Listening…',
  thinking: 'सोच रही हूँ…',
  speaking: 'Saathi बोल रही हैं…',
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
  const [view, setView] = useState<'landing' | 'session'>('landing');
  const [connectingLanguage, setConnectingLanguage] = useState<Language | null>(null);
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
    if (!errorMessage) return;
    const timeout = setTimeout(() => setErrorMessage(null), 6000);
    return () => clearTimeout(timeout);
  }, [errorMessage]);

  // User-gesture-triggered (language tap), so no StrictMode double-run to
  // guard against -- the connectingLanguage state blocks double taps, and
  // the tap itself unlocks the AudioContext so the greeting can autoplay.
  async function beginSession(language: Language) {
    if (connectingLanguage) return;
    setConnectingLanguage(language);
    void unlockAudio();
    try {
      const result = await postSession(language);
      sessionIdRef.current = result.session_id;
      setCurrentUi(result.ui);
      setSessionReady(true);
      setView('session');
      setTalkState('speaking');
      try {
        await playBase64Mp3(result.greeting_audio_b64);
      } catch (err) {
        // Autoplay refused (rare -- the tap unlocked us): stash the greeting
        // to play on her first button press instead, like the old flow.
        console.error('[talk] greeting autoplay failed:', err);
        greetingAudioRef.current = result.greeting_audio_b64;
      }
      setTalkState('ready');
    } catch (err) {
      console.error('[talk] could not start session:', err);
      setErrorMessage(
        err instanceof Error ? err.message : 'Could not reach the mentor. Try reloading.',
      );
      setConnectingLanguage(null);
    }
  }

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
            <Landing connectingLanguage={connectingLanguage} onPick={beginSession} />
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
                    <Renderer ui={currentUi} onTapOption={handleTapOption} />
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
                  {sessionReady ? STATUS_LABELS[talkState] : 'connecting…'}
                </motion.p>
              </AnimatePresence>
              <TalkButton
                state={talkState}
                disabled={!sessionReady}
                onPressStart={handlePressStart}
                onPressEnd={handlePressEnd}
              />
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
