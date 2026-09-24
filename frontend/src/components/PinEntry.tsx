import { motion, AnimatePresence } from 'motion/react';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Keypad } from './Keypad';
import { SaathiAvatar } from './SaathiAvatar';

interface Props {
  checking: boolean;
  error: string | null;
  attemptsLeft: number;
  onSubmit: (pin: string) => void;
  onBack: () => void;
  onStartFresh: () => void;
}

const MAX_LOCAL_ATTEMPTS = 5;

/** Pre-conversation PIN login (login roadmap item 1): the keypad is
 * available from the very start here, not only after voice fails -- a
 * returning learner can skip the voice conversation entirely. */
export function PinEntry({ checking, error, attemptsLeft, onSubmit, onBack, onStartFresh }: Props) {
  const outOfTries = attemptsLeft <= 0;

  return (
    <motion.div
      className="flex min-h-full flex-col items-center gap-6 px-6 py-10 text-center [justify-content:safe_center]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <button
        type="button"
        onClick={onBack}
        className="absolute left-4 top-4 flex items-center gap-1 text-sm font-medium text-brand-700"
      >
        <ArrowLeft className="size-4" /> वापस · Back
      </button>

      <SaathiAvatar size="md" />

      <h2 className="max-w-sm text-2xl font-bold text-foreground">
        अपना 4 अंकों का PIN डालिए
        <br />
        <span className="text-lg font-medium text-muted-foreground">
          Enter your 4-digit PIN
        </span>
      </h2>

      <Keypad onSubmit={onSubmit} disabled={checking || outOfTries} />

      <AnimatePresence mode="wait">
        {error && !outOfTries && (
          <motion.p
            key="error"
            role="alert"
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="max-w-xs text-base font-medium text-destructive"
          >
            {error} · {attemptsLeft} {attemptsLeft === 1 ? 'try' : 'tries'} left
          </motion.p>
        )}
      </AnimatePresence>

      {outOfTries && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex flex-col items-center gap-3"
        >
          <p className="max-w-xs text-base font-medium text-muted-foreground">
            PIN मेल नहीं खा रहा · PIN isn't matching. You can start fresh, or go back and try
            speaking it instead.
          </p>
          <Button onClick={onStartFresh}>नए सिरे से शुरू करें · Start Fresh</Button>
        </motion.div>
      )}
    </motion.div>
  );
}

export { MAX_LOCAL_ATTEMPTS };
