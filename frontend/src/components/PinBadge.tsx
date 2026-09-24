import { motion } from 'motion/react';
import { KeyRound } from 'lucide-react';

interface Props {
  pin: string;
}

/** A new learner's 4-digit code, pinned in one corner for the whole
 * session (login roadmap item 1) -- not shown once and forgotten, since
 * that's exactly when a low-literacy user needs it most: right when she
 * first needs to remember it for next time. */
export function PinBadge({ pin }: Props) {
  return (
    <motion.div
      className="fixed bottom-4 left-3 z-20 flex items-center gap-2 rounded-2xl bg-brand-700/95 px-3 py-2 text-white shadow-lg backdrop-blur"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      role="status"
      aria-label={`Your PIN is ${pin.split('').join(' ')}`}
    >
      <KeyRound className="size-4 shrink-0" />
      <span className="flex flex-col leading-tight">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-brand-100">
          आपका PIN · Your PIN
        </span>
        <span className="text-lg font-black tracking-[0.3em]">{pin}</span>
      </span>
    </motion.div>
  );
}
