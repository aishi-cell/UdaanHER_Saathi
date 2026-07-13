import { motion } from 'motion/react';
import { Loader2, Mic } from 'lucide-react';
import { cn } from '@/lib/utils';

export type TalkState = 'ready' | 'listening' | 'thinking' | 'speaking';

interface Props {
  state: TalkState;
  disabled?: boolean;
  onPressStart: () => void;
  onPressEnd: () => void;
}

const BUTTON_GRADIENT: Record<TalkState, string> = {
  ready: 'from-brand-500 to-brand-700',
  listening: 'from-red-500 to-brand-700',
  thinking: 'from-brand-300 to-brand-400',
  speaking: 'from-sun-400 to-brand-500',
};

function Waveform() {
  return (
    <span className="flex h-14 items-end gap-1.5" aria-hidden>
      {[0, 1, 2, 3, 4].map((i) => (
        <motion.span
          key={i}
          className="w-2.5 rounded-full bg-white"
          animate={{ height: ['0.9rem', '3.2rem', '0.9rem'] }}
          transition={{ repeat: Infinity, duration: 0.9, delay: i * 0.12, ease: 'easeInOut' }}
        />
      ))}
    </span>
  );
}

function ListeningRipples() {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          aria-hidden
          className="absolute inset-0 rounded-full border-4 border-red-400/60"
          initial={{ scale: 1, opacity: 0.8 }}
          animate={{ scale: 1.55, opacity: 0 }}
          transition={{ repeat: Infinity, duration: 1.6, delay: i * 0.5, ease: 'easeOut' }}
        />
      ))}
    </>
  );
}

export function TalkButton({ state, disabled, onPressStart, onPressEnd }: Props) {
  return (
    <div className="relative">
      {state === 'listening' && <ListeningRipples />}
      <motion.button
        type="button"
        aria-label="Hold to talk"
        className={cn(
          'relative flex size-40 items-center justify-center rounded-full bg-gradient-to-br text-white shadow-2xl shadow-brand-500/40 select-none sm:size-44',
          BUTTON_GRADIENT[state],
          state === 'ready' && !disabled && 'animate-breathe',
          disabled && 'opacity-50',
        )}
        animate={{ scale: state === 'listening' ? 1.12 : 1 }}
        whileTap={state === 'ready' && !disabled ? { scale: 1.08 } : undefined}
        transition={{ type: 'spring', stiffness: 300, damping: 20 }}
        onPointerDown={onPressStart}
        onPointerUp={onPressEnd}
        onPointerLeave={onPressEnd}
        onContextMenu={(e) => e.preventDefault()}
      >
        {state === 'thinking' ? (
          <Loader2 className="size-16 animate-spin" strokeWidth={2.5} />
        ) : state === 'speaking' ? (
          <Waveform />
        ) : (
          <Mic className="size-16" strokeWidth={2.2} />
        )}
      </motion.button>
    </div>
  );
}
