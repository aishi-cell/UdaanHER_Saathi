import { useState } from 'react';
import { motion } from 'motion/react';
import { Delete } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface Props {
  /** Called once 4 digits are entered -- the digit string, e.g. "4271". */
  onSubmit: (pin: string) => void;
  disabled?: boolean;
}

const DIGITS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', 'back'] as const;

/** A large-target number pad for entering a 4-digit PIN by tap, so it never
 * depends on voice recognition working (login roadmap item 1). Submits
 * automatically the moment the 4th digit is tapped. */
export function Keypad({ onSubmit, disabled }: Props) {
  const [digits, setDigits] = useState('');

  function tap(key: string) {
    if (disabled) return;
    if (key === 'back') {
      setDigits((d) => d.slice(0, -1));
      return;
    }
    if (key === '' || digits.length >= 4) return;
    const next = digits + key;
    setDigits(next);
    if (next.length === 4) {
      onSubmit(next);
      setDigits('');
    }
  }

  return (
    <div className="flex w-full max-w-xs flex-col items-center gap-5">
      <div className="flex gap-3" aria-label="PIN entered so far">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className="flex size-11 items-center justify-center rounded-2xl border-2 border-brand-200 bg-white/80 text-2xl font-black text-brand-900"
          >
            {digits[i] ?? ''}
          </span>
        ))}
      </div>
      <div className="grid w-full grid-cols-3 gap-3">
        {DIGITS.map((key, i) =>
          key === '' ? (
            <span key={`blank-${i}`} />
          ) : (
            <motion.button
              key={key}
              type="button"
              disabled={disabled}
              onClick={() => tap(key)}
              whileTap={{ scale: 0.92 }}
              className="flex h-16 items-center justify-center rounded-2xl bg-white/85 text-2xl font-bold text-brand-900 shadow-md shadow-brand-200/40 backdrop-blur disabled:opacity-50"
              aria-label={key === 'back' ? 'Delete last digit' : `Digit ${key}`}
            >
              {key === 'back' ? <Delete className="size-6" /> : key}
            </motion.button>
          ),
        )}
      </div>
      {digits.length > 0 && (
        <Button variant="ghost" size="sm" onClick={() => setDigits('')} disabled={disabled}>
          साफ़ करें · Clear
        </Button>
      )}
    </div>
  );
}
