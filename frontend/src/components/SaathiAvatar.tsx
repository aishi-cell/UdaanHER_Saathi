import { motion } from 'motion/react';
import { cn } from '@/lib/utils';

/**
 * The illustrated Saathi didi inside concentric lavender rings, flanked by a
 * decorative waveform — the mockup's central motif. Pure SVG, no assets.
 * `talking` animates the rings and waveform (used while she speaks/listens).
 */

function SaathiFace({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 120 120" className={className} aria-hidden>
      {/* dupatta / hair backdrop */}
      <circle cx="60" cy="60" r="56" fill="#f3eefe" />
      <path
        d="M60 14c-26 0-40 20-40 42v28c0 4 4 6 8 6h64c4 0 8-2 8-6V56c0-22-14-42-40-42z"
        fill="#4c2a63"
      />
      {/* face */}
      <ellipse cx="60" cy="62" rx="24" ry="26" fill="#eeb98f" />
      {/* hair parting */}
      <path
        d="M60 30c-16 0-26 12-27 28 6-14 16-18 27-18s21 4 27 18c-1-16-11-28-27-28z"
        fill="#3b2050"
      />
      {/* bindi */}
      <circle cx="60" cy="46" r="2.2" fill="#db2777" />
      {/* eyes */}
      <ellipse cx="51" cy="60" rx="3" ry="3.6" fill="#2b2145" />
      <ellipse cx="69" cy="60" rx="3" ry="3.6" fill="#2b2145" />
      <path
        d="M46 54c2-2.5 8-2.5 10 0"
        stroke="#3b2050"
        strokeWidth="1.6"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M64 54c2-2.5 8-2.5 10 0"
        stroke="#3b2050"
        strokeWidth="1.6"
        fill="none"
        strokeLinecap="round"
      />
      {/* nose + smile */}
      <path d="M60 63v6" stroke="#d69a6e" strokeWidth="1.6" strokeLinecap="round" />
      <path
        d="M52 74c3 4 13 4 16 0"
        stroke="#b85450"
        strokeWidth="2.4"
        fill="none"
        strokeLinecap="round"
      />
      {/* earrings */}
      <circle cx="36.5" cy="66" r="2.4" fill="#ffb63f" />
      <circle cx="83.5" cy="66" r="2.4" fill="#ffb63f" />
      {/* dupatta drape over shoulder */}
      <path d="M20 96c8-10 24-14 40-14s32 4 40 14v10H20V96z" fill="#ec4899" opacity="0.9" />
      <path d="M20 100c10-8 24-11 40-11s30 3 40 11v6H20v-6z" fill="#db2777" opacity="0.6" />
    </svg>
  );
}

function WaveBars({ side, talking }: { side: 'left' | 'right'; talking: boolean }) {
  const heights = side === 'left' ? [10, 22, 14, 30, 18] : [18, 30, 14, 22, 10];
  return (
    <div
      className={cn('flex items-center gap-1.5', side === 'left' && 'flex-row-reverse')}
      aria-hidden
    >
      {heights.map((h, i) => (
        <motion.span
          key={i}
          className="w-1.5 rounded-full bg-brand-300"
          style={{ height: h }}
          animate={talking ? { scaleY: [1, 1.7, 0.7, 1] } : { scaleY: 1 }}
          transition={
            talking
              ? { repeat: Infinity, duration: 1.1, delay: i * 0.12, ease: 'easeInOut' }
              : undefined
          }
        />
      ))}
    </div>
  );
}

interface Props {
  talking?: boolean;
  size?: 'md' | 'lg';
  className?: string;
}

export function SaathiAvatar({ talking = false, size = 'lg', className }: Props) {
  const dim = size === 'lg' ? 'size-40 sm:size-44' : 'size-28';
  return (
    <div className={cn('flex items-center gap-4 sm:gap-6', className)}>
      <WaveBars side="left" talking={talking} />
      <div className={cn('relative', dim)}>
        {/* concentric rings */}
        <motion.span
          className="absolute -inset-6 rounded-full border border-brand-200/80 bg-brand-50/60"
          animate={talking ? { scale: [1, 1.06, 1] } : {}}
          transition={{ repeat: Infinity, duration: 1.6, ease: 'easeInOut' }}
          aria-hidden
        />
        <motion.span
          className="absolute -inset-3 rounded-full border border-brand-200 bg-brand-100/70"
          animate={talking ? { scale: [1, 1.04, 1] } : {}}
          transition={{ repeat: Infinity, duration: 1.6, delay: 0.15, ease: 'easeInOut' }}
          aria-hidden
        />
        <div className="absolute inset-0 overflow-hidden rounded-full shadow-lg shadow-brand-300/40 ring-4 ring-white">
          <SaathiFace className="size-full" />
        </div>
      </div>
      <WaveBars side="right" talking={talking} />
    </div>
  );
}
