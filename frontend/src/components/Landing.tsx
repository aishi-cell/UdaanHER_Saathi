import { motion } from 'motion/react';
import { Bird, BookOpen, Heart, IndianRupee, Loader2, Mic } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SaathiAvatar } from './SaathiAvatar';

export type Language = 'gu-IN' | 'hi-IN' | 'en-IN';

interface Props {
  connecting: boolean;
  onStart: () => void;
}

const FEATURES = [
  { icon: Mic, title: 'Voice First', sub: 'Speak naturally, we understand.' },
  { icon: BookOpen, title: 'Learn by Doing', sub: 'Short lessons from real tutorials.' },
  { icon: IndianRupee, title: 'Earn with Skills', sub: 'Make, sell and grow your income.' },
];

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.1, delayChildren: 0.05 } },
};
const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: 'spring' as const, stiffness: 130, damping: 17 } },
};

export function Landing({ connecting, onStart }: Props) {
  return (
    <motion.div
      key="hero"
      className="flex h-full flex-col items-center justify-center gap-8 px-6 py-10 text-center"
      variants={container}
      initial="hidden"
      animate="show"
      exit={{ opacity: 0, x: -32 }}
      transition={{ duration: 0.25 }}
    >
      <motion.div variants={item} className="flex flex-col items-center gap-2">
        <h1 className="flex items-center gap-2 text-5xl font-black tracking-tight text-brand-800">
          Udaan
          <Bird className="size-9 -scale-x-100 text-blush-500" strokeWidth={2.2} />
        </h1>
        <p className="text-2xl font-bold text-blush-600">Her Saathi</p>
      </motion.div>

      <motion.div variants={item}>
        <SaathiAvatar size="md" />
      </motion.div>

      <motion.div variants={item} className="flex flex-col items-center gap-3">
        <h2 className="max-w-md text-3xl font-extrabold leading-tight text-foreground sm:text-4xl">
          A voice mentor that helps you learn skills and earn with confidence.
        </h2>
        <p className="max-w-sm text-lg text-muted-foreground">
          Personalized. Practical. In your language.
          <br />
          No reading. Just your voice.
        </p>
      </motion.div>

      <motion.div variants={item}>
        <Button
          size="lg"
          disabled={connecting}
          onClick={onStart}
          className="h-16 rounded-full bg-brand-700 px-10 text-xl font-semibold shadow-lg shadow-brand-400/40 hover:bg-brand-800"
        >
          {connecting ? (
            <>
              <Loader2 className="size-6 animate-spin" /> Saathi आ रही हैं…
            </>
          ) : (
            <>
              <Mic className="size-6" /> Talk to Saathi
            </>
          )}
        </Button>
      </motion.div>

      <motion.div variants={item} className="grid w-full max-w-xl grid-cols-3 gap-3">
        {FEATURES.map((f) => (
          <div
            key={f.title}
            className="flex flex-col items-center gap-1.5 rounded-2xl bg-white/70 px-3 py-4 backdrop-blur"
          >
            <span className="flex size-11 items-center justify-center rounded-full bg-brand-100 text-brand-700">
              <f.icon className="size-5" />
            </span>
            <span className="text-sm font-bold text-foreground">{f.title}</span>
            <span className="text-xs leading-snug text-muted-foreground">{f.sub}</span>
          </div>
        ))}
      </motion.div>

      <motion.p
        variants={item}
        className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground"
      >
        Built for rural women. By women.
        <Heart className="size-4 fill-blush-500 text-blush-500" />
      </motion.p>
    </motion.div>
  );
}
