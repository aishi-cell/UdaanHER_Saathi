import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Compass, MicOff } from 'lucide-react';
import {
  ApiError,
  getHealth,
  getJourney,
  postLearnerLookup,
  postSession,
  postTurn,
  type TurnResponse,
} from './api';
import { MicPermissionDeniedError, PushToTalkRecorder } from './audio/recorder';
import { playBase64Mp3, playEarcon, unlockAudio } from './audio/player';
import { SpeechWatcher } from './audio/vad';
import { AuroraBackground } from './components/AuroraBackground';
import { JourneyView } from './components/JourneyView';
import { Landing } from './components/Landing';
import { PinBadge } from './components/PinBadge';
import { PinEntry, MAX_LOCAL_ATTEMPTS } from './components/PinEntry';
import { Renderer } from './components/Renderer';
import { SaathiAvatar } from './components/SaathiAvatar';
import { TalkButton, type TalkState } from './components/TalkButton';
import { UiDemo } from './UiDemo';
import {
  clearRememberedLogin,
  getRememberedLogin,
  setRememberedLogin,
} from './lib/rememberedLogin';
import { cn } from '@/lib/utils';
import type { JourneyPayload, SessionLanguage, UICommand } from './types';

/** A random 4-digit code for a new learner, generated client-side the
 * moment she says she's new so it can be pinned on screen right away
 * (login roadmap item 1), before the onboarding conversation even starts. */
function generatePin(): string {
  const bytes = new Uint8Array(2);
  crypto.getRandomValues(bytes);
  const n = ((bytes[0] << 8) | bytes[1]) % 10_000;
  return n.toString().padStart(4, '0');
}

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
  const [view, setView] = useState<'landing' | 'pin-entry' | 'session'>('landing');
  const [connecting, setConnecting] = useState(false);
  const [backendUp, setBackendUp] = useState<boolean | null>(null);
  const [talkState, setTalkState] = useState<TalkState>('ready');
  const [micDenied, setMicDenied] = useState(false);
  const [lastTurn, setLastTurn] = useState<TurnResponse | null>(null);
  const [currentUi, setCurrentUi] = useState<UICommand>(IDLE_UI);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [sessionReady, setSessionReady] = useState(false);

  // Login roadmap item 1: PIN keypad entry, a persistent corner PIN badge
  // for a new learner, and "remember this phone" for a returning one.
  const [pinChecking, setPinChecking] = useState(false);
  const [pinError, setPinError] = useState<string | null>(null);
  const [pinAttemptsLeft, setPinAttemptsLeft] = useState(MAX_LOCAL_ATTEMPTS);
  const [activePin, setActivePin] = useState<string | null>(null);
  const [usingRememberedLogin, setUsingRememberedLogin] = useState(false);

  // Career roadmap (roadmap item 3): "My Journey" -- a plain read from the
  // REST endpoint, independent of the turn-based conversation.
  const [learnerId, setLearnerId] = useState<string | null>(null);
  const [journey, setJourney] = useState<JourneyPayload | null>(null);
  const [journeyLoading, setJourneyLoading] = useState(false);

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

  // The moment her profile (and PIN) is saved -- whether or not she came in
  // through the "I'm new" button -- pin it in the corner and remember this
  // phone for next time, same as a keypad login does.
  useEffect(() => {
    if (currentUi.type !== 'show_profile_card' || !currentUi.profile.pin) return;
    const { name, pin } = currentUi.profile;
    setActivePin(pin);
    setRememberedLogin({ name, pin });
  }, [currentUi]);

  // "Remember this phone" (login roadmap item 1): if she used Saathi here
  // before and chose to be remembered, skip straight to resuming -- no code
  // to re-enter. A visible "Not you?" escape hatch clears it if she's wrong.
  useEffect(() => {
    const remembered = getRememberedLogin();
    if (!remembered) return;
    setUsingRememberedLogin(true);
    void unlockAudio();
    void startSession({ learnerName: remembered.name, pin: remembered.pin });
    // Mount-only: this is a one-shot check of what the phone remembers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Shared session start for every entry path: the voice-first hero
   * button, remembered-phone auto-resume, PIN-keypad login, and the
   * new-user flow (which pre-shows her code via pendingPin). */
  async function startSession(opts: {
    language?: SessionLanguage;
    learnerName?: string;
    pin?: string;
    pendingPin?: string;
  } = {}) {
    if (connecting) return;
    setConnecting(true);
    void unlockAudio();
    setView('session');
    try {
      const result = await postSession(opts.language, opts.learnerName, opts.pin, opts.pendingPin);
      sessionIdRef.current = result.session_id;
      setLearnerId(result.learner_id);
      // Bug found via a logout live-test: this was never reset to false on
      // success, so the Landing button was stuck showing "connecting..."
      // (and disabled) forever after navigating back there -- e.g. from
      // "Not you?" -- even though nothing was actually in flight anymore.
      setConnecting(false);
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
      setUsingRememberedLogin(false);
      setView('landing');
    }
  }

  function beginSession() {
    void startSession();
  }

  function goToPinEntry() {
    setPinError(null);
    setPinAttemptsLeft(MAX_LOCAL_ATTEMPTS);
    setView('pin-entry');
  }

  async function submitPinEntry(pin: string) {
    setPinChecking(true);
    setPinError(null);
    try {
      const result = await postLearnerLookup(pin);
      if (!result.found || !result.learner_name) {
        setPinAttemptsLeft((n) => Math.max(0, n - 1));
        setPinError('PIN नहीं मिला · PIN not found');
        return;
      }
      setRememberedLogin({ name: result.learner_name, pin });
      void unlockAudio();
      await startSession({ learnerName: result.learner_name, pin });
    } catch (err) {
      console.error('[talk] PIN lookup failed:', err);
      setPinError(friendlyErrorMessage(err));
    } finally {
      setPinChecking(false);
    }
  }

  function startAsNewUser() {
    const pin = generatePin();
    setActivePin(pin);
    void unlockAudio();
    void startSession({ pendingPin: pin });
  }

  function backToLanding() {
    setView('landing');
    setPinError(null);
  }

  function forgetThisPhone() {
    void stopRecorder(); // don't leave the mic listening in the background
    clearRememberedLogin();
    setUsingRememberedLogin(false);
    setSessionReady(false);
    sessionIdRef.current = null;
    setLearnerId(null);
    setJourney(null);
    setView('landing');
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
      if (result.learner_id) setLearnerId(result.learner_id);
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

  /** Career roadmap (roadmap item 3): a plain read, doesn't touch the
   * conversation graph -- pause listening first so an open journey screen
   * doesn't get interrupted by an accidental turn being sent. */
  async function openJourney() {
    if (!learnerId || journeyLoading) return;
    if (talkState === 'listening') await discardListening();
    setJourneyLoading(true);
    try {
      const data = await getJourney(learnerId);
      setJourney(data);
    } catch (err) {
      console.error('[talk] could not load journey:', err);
      setErrorMessage(friendlyErrorMessage(err));
    } finally {
      setJourneyLoading(false);
    }
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

      {/* Backend status dot: a developer indicator, not something a learner
          can act on -- an unreachable backend already surfaces as a warm
          error message the moment she tries to do something (roadmap item
          6: hide anything that doesn't help the learner). Debug-only. */}
      {isDebug && (
        <span
          className={cn(
            'absolute right-4 top-4 z-20 size-3 rounded-full transition-colors',
            backendUp ? 'bg-emerald-500' : 'bg-red-500',
            backendUp && 'shadow-[0_0_8px_2px_rgb(16_185_129/0.5)]',
          )}
          aria-label={backendUp ? 'Backend connected' : 'Backend unreachable'}
        />
      )}

      {/* Login roadmap item 1: her code, pinned in one corner for the whole
          session -- shown as soon as it exists, new-user or freshly saved. */}
      {view === 'session' && activePin && <PinBadge pin={activePin} />}

      <AnimatePresence mode="wait">
        {view === 'landing' ? (
          <motion.div
            key="landing"
            className="h-full overflow-y-auto"
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.35 }}
          >
            <Landing
              connecting={connecting}
              onStart={beginSession}
              onPinEntry={goToPinEntry}
              onNewUser={startAsNewUser}
            />
          </motion.div>
        ) : view === 'pin-entry' ? (
          <motion.div key="pin-entry" className="relative h-full overflow-y-auto">
            <PinEntry
              checking={pinChecking}
              error={pinError}
              attemptsLeft={pinAttemptsLeft}
              onSubmit={submitPinEntry}
              onBack={backToLanding}
              onStartFresh={backToLanding}
            />
          </motion.div>
        ) : (
          <motion.div
            key="session"
            className="flex h-full flex-col"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4 }}
          >
            <header className="relative flex flex-col items-center gap-1 pt-5">
              {/* Career roadmap (roadmap item 3): reachable any time once
                  she's identified, without spending a conversation turn. */}
              {learnerId && (
                <button
                  type="button"
                  onClick={openJourney}
                  disabled={journeyLoading}
                  className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-white/80 px-3 py-1.5 text-xs font-semibold text-brand-700 shadow-sm backdrop-blur disabled:opacity-60"
                >
                  <Compass className="size-3.5" /> मेरी Journey
                </button>
              )}
              <span className="text-lg font-bold tracking-tight text-brand-600">
                UdaanHER <span className="text-blush-600">Saathi</span>
              </span>
              {/* Login roadmap item 1: "log out on this phone" -- a small,
                  always-available escape hatch for the whole session, not
                  just the first moment, since a remembered login might turn
                  out wrong only once she hears her own (or someone else's)
                  name in the greeting. */}
              {usingRememberedLogin && (
                <button
                  type="button"
                  onClick={forgetThisPhone}
                  className="text-xs font-medium text-muted-foreground underline"
                >
                  आप नहीं हैं? · Not you? (log out)
                </button>
              )}
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

      <AnimatePresence>
        {journey && <JourneyView journey={journey} onClose={() => setJourney(null)} />}
      </AnimatePresence>
    </div>
  );
}

export default App;
