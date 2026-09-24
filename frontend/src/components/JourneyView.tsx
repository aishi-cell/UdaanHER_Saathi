import { motion } from 'motion/react';
import { CheckCircle2, Circle, X } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { JourneyPayload } from '../types';

interface Props {
  journey: JourneyPayload;
  onClose: () => void;
}

/** Career roadmap ("My Journey", roadmap item 3): the bigger arc across a
 * skill -- large icons, minimal text, completed vs. upcoming steps, per the
 * roadmap's own description of this screen. Voice remains the primary way
 * she hears this (Saathi narrates it); this is the supporting visual. */
export function JourneyView({ journey, onClose }: Props) {
  return (
    <motion.div
      className="fixed inset-0 z-40 flex items-center justify-center bg-foreground/40 p-4 backdrop-blur-sm"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <Card
        className="relative w-full max-w-md border-brand-100 bg-white/95 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="absolute right-4 top-4 z-10 flex size-9 items-center justify-center rounded-full bg-brand-50 text-brand-700"
        >
          <X className="size-5" />
        </button>
        <CardContent className="flex flex-col gap-5 p-6 pt-8 sm:p-8 sm:pt-10">
          <p className="text-center text-2xl font-extrabold text-foreground">
            मेरी Journey · My Journey
          </p>

          <ul className="flex flex-col gap-3">
            {journey.milestones.map((m, i) => (
              <motion.li
                key={m.milestone_id}
                className={cn(
                  'flex items-center gap-4 rounded-2xl px-4 py-3',
                  m.achieved ? 'bg-emerald-50' : 'bg-muted/60',
                )}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.06 }}
              >
                {m.achieved ? (
                  <CheckCircle2 className="size-8 shrink-0 text-emerald-600" />
                ) : (
                  <Circle className="size-8 shrink-0 text-muted-foreground/50" />
                )}
                <div className="flex flex-col">
                  <span
                    className={cn(
                      'text-lg font-bold',
                      m.achieved ? 'text-emerald-900' : 'text-foreground/70',
                    )}
                  >
                    {m.label_hi}
                  </span>
                  <span className="text-sm text-muted-foreground">{m.label_en}</span>
                  {!m.achieved && !m.auto_tracked && (
                    <span className="mt-0.5 text-xs font-medium text-brand-600">
                      हो जाए तो Saathi को बताइए · Tell Saathi when this happens
                    </span>
                  )}
                </div>
              </motion.li>
            ))}
          </ul>

          <p className="rounded-xl bg-accent px-4 py-3 text-center text-base font-medium text-accent-foreground">
            {journey.next_step_text}
          </p>
        </CardContent>
      </Card>
    </motion.div>
  );
}
