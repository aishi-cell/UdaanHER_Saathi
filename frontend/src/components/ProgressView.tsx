import { motion } from 'motion/react';
import { ArrowRight, CheckCircle2, Lock, Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import type { ProgressPayload } from '../types';

interface Props {
  payload: ProgressPayload;
}

const MASTERY_STYLE: Record<ProgressPayload['concepts'][number]['mastery'], string> = {
  strong: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  shaky: 'bg-amber-100 text-amber-800 border-amber-300',
  unseen: 'bg-muted text-muted-foreground border-border',
};

function LessonIcon({ status }: { status: ProgressPayload['lessons'][number]['status'] }) {
  if (status === 'done') return <CheckCircle2 className="size-6 shrink-0 text-emerald-600" />;
  if (status === 'current') return <ArrowRight className="size-6 shrink-0 text-brand-500" />;
  return <Lock className="size-5 shrink-0 text-muted-foreground" />;
}

export function ProgressView({ payload }: Props) {
  const done = payload.lessons.filter((lesson) => lesson.status === 'done').length;
  const percent = payload.lessons.length ? Math.round((done / payload.lessons.length) * 100) : 0;

  return (
    <Card className="w-full max-w-xl border-brand-100 bg-white/85 shadow-xl shadow-brand-200/40 backdrop-blur">
      <CardContent className="flex flex-col gap-6 p-6 sm:p-8">
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <p className="text-2xl font-bold capitalize text-brand-900">{payload.skill}</p>
            <span className="text-lg font-semibold text-brand-600">{percent}%</span>
          </div>
          <Progress value={percent} className="h-3 bg-brand-100" />
        </div>

        <ul className="flex flex-col gap-3">
          {payload.lessons.map((lesson, i) => (
            <motion.li
              key={lesson.lesson_id}
              className={cn(
                'flex items-center gap-3 rounded-xl px-4 py-3 text-lg font-medium',
                lesson.status === 'current' ? 'bg-brand-50 text-brand-900' : 'text-foreground/80',
              )}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.07 }}
            >
              <LessonIcon status={lesson.status} />
              <span className="capitalize">{lesson.title}</span>
            </motion.li>
          ))}
        </ul>

        <div className="flex flex-wrap gap-2">
          {payload.concepts.map((concept, i) => (
            <motion.span
              key={concept.concept_id}
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2 + i * 0.05 }}
            >
              <Badge
                variant="outline"
                className={cn('px-3 py-1.5 text-sm font-medium', MASTERY_STYLE[concept.mastery])}
              >
                {concept.label}
              </Badge>
            </motion.span>
          ))}
        </div>

        {payload.next_step_text && (
          <p className="flex items-start gap-2 rounded-xl bg-accent px-4 py-3 text-base font-medium text-accent-foreground">
            <Sparkles className="mt-0.5 size-5 shrink-0" />
            {payload.next_step_text}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
