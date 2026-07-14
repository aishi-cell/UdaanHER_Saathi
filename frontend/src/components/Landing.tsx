import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Bird, BookOpen, Check, Heart, IndianRupee, Loader2, Mic } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { SaathiAvatar } from './SaathiAvatar';

export type Language = 'gu-IN' | 'hi-IN' | 'en-IN';

interface Props {
  connectingLanguage: Language | null;
  onPick: (language: Language) => void;
}

const LANGUAGES: { code: Language; label: string; sub?: string }[] = [
  { code: 'hi-IN', label: 'हिन्दी', sub: 'Hindi' },
  { code: 'gu-IN', label: 'ગુજરાતી', sub: 'Gujarati' },
  { code: 'en-IN', label: 'English' },
];

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

function Hero({ onStart }: { onStart: () => void }) {
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
        <p className="max-w-sm text-base text-muted-foreground">
          Personalized. Practical. In your language.
          <br />
          No reading. Just your voice.
        </p>
      </motion.div>

      <motion.div variants={item}>
        <Button
          size="lg"
          onClick={onStart}
          className="h-16 gap-3 rounded-2xl bg-brand-700 px-10 text-xl font-semibold shadow-lg shadow-brand-400/40 hover:bg-brand-800"
        >
          <Mic className="size-6" /> Talk to Saathi
        </Button>
      </motion.div>

      <motion.div variants={item} className="grid w-full max-w-lg grid-cols-3 gap-3">
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

function LanguagePick({
  connectingLanguage,
  onPick,
}: {
  connectingLanguage: Language | null;
  onPick: (language: Language) => void;
}) {
  const [selected, setSelected] = useState<Language>('hi-IN');
  const connecting = connectingLanguage !== null;

  return (
    <motion.div
      key="language"
      className="flex h-full flex-col items-center justify-center gap-8 px-6 py-10 text-center"
      initial={{ opacity: 0, x: 32 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -32 }}
      transition={{ duration: 0.25 }}
    >
      <div className="flex flex-col items-center gap-2">
        <h2 className="text-3xl font-extrabold text-foreground">Choose your language</h2>
        <p className="text-base text-muted-foreground">You can change it anytime</p>
      </div>

      <div className="flex w-full max-w-sm flex-col gap-3">
        {LANGUAGES.map((lang) => {
          const isSelected = selected === lang.code;
          return (
            <motion.button
              key={lang.code}
              type="button"
              disabled={connecting}
              onClick={() => setSelected(lang.code)}
              className={cn(
                'flex min-h-16 items-center justify-between rounded-2xl border-2 bg-white px-6 shadow-sm transition-colors',
                isSelected
                  ? 'border-brand-500 bg-brand-50'
                  : 'border-border hover:border-brand-300',
                connecting && !isSelected && 'opacity-40',
              )}
              whileTap={connecting ? undefined : { scale: 0.98 }}
            >
              <span className="text-2xl font-bold text-foreground">{lang.label}</span>
              <span className="flex items-center gap-2">
                {lang.sub && <span className="text-sm text-muted-foreground">{lang.sub}</span>}
                {isSelected && <Check className="size-6 text-brand-600" strokeWidth={3} />}
              </span>
            </motion.button>
          );
        })}
      </div>

      <Button
        size="lg"
        disabled={connecting}
        onClick={() => onPick(selected)}
        className="h-16 w-full max-w-sm rounded-2xl bg-brand-700 text-xl font-semibold shadow-lg shadow-brand-400/40 hover:bg-brand-800"
      >
        {connecting ? (
          <>
            <Loader2 className="size-6 animate-spin" /> Saathi आ रही हैं…
          </>
        ) : (
          'Continue'
        )}
      </Button>
    </motion.div>
  );
}

export function Landing({ connectingLanguage, onPick }: Props) {
  const [step, setStep] = useState<'hero' | 'language'>('hero');

  return (
    <AnimatePresence mode="wait">
      {step === 'hero' ? (
        <Hero key="hero" onStart={() => setStep('language')} />
      ) : (
        <LanguagePick key="language" connectingLanguage={connectingLanguage} onPick={onPick} />
      )}
    </AnimatePresence>
  );
}
