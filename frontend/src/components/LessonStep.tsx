import { motion } from 'motion/react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { ShowLessonStepCommand } from '../types';

interface Props {
  step: ShowLessonStepCommand;
}

export function LessonStep({ step }: Props) {
  return (
    <Card className="w-full max-w-xl border-brand-100 bg-white/85 shadow-xl shadow-brand-200/40 backdrop-blur">
      <CardContent className="flex flex-col items-center gap-5 p-6 sm:p-8">
        <Badge className="bg-secondary px-4 py-1.5 text-base font-semibold text-secondary-foreground">
          Step {step.step_index + 1} of {step.total_steps}
        </Badge>

        {step.image && (
          <motion.img
            key={step.step_index}
            src={step.image}
            alt=""
            className="max-h-[36vh] w-full rounded-2xl object-contain"
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.35 }}
          />
        )}

        <p className="text-center text-2xl font-semibold leading-snug text-brand-900 sm:text-3xl">
          {step.caption}
        </p>

        <div className="flex gap-2" aria-hidden>
          {Array.from({ length: step.total_steps }).map((_, i) => (
            <span
              key={i}
              className={cn(
                'size-3 rounded-full transition-colors',
                i === step.step_index ? 'scale-110 bg-brand-500' : 'bg-brand-200',
              )}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
