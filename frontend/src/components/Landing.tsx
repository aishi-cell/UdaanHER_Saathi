import { motion } from 'motion/react';
import { Loader2, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

export type Language = 'gu-IN' | 'hi-IN' | 'en-IN';

interface Props {
  connectingLanguage: Language | null;
  onPick: (language: Language) => void;
}

const LANGUAGES: { code: Language; label: string; sub: string }[] = [
  { code: 'gu-IN', label: 'ગુજરાતી', sub: 'Gujarati' },
  { code: 'hi-IN', label: 'हिन्दी', sub: 'Hindi' },
  { code: 'en-IN', label: 'English', sub: 'English' },
];

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.12, delayChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { type: 'spring' as const, stiffness: 120, damping: 16 } },
};

export function Landing({ connectingLanguage, onPick }: Props) {
  const connecting = connectingLanguage !== null;

  return (
    <motion.div
      className="flex h-full flex-col items-center justify-center gap-10 px-6 py-10 text-center"
      variants={container}
      initial="hidden"
      animate="show"
    >
      <motion.div variants={item} className="flex flex-col items-center gap-5">
        <motion.div
          className="flex size-24 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-sun-400 text-white shadow-xl shadow-brand-500/30"
          animate={{ rotate: [0, 6, -6, 0] }}
          transition={{ repeat: Infinity, duration: 6, ease: 'easeInOut' }}
        >
          <Sparkles className="size-12" strokeWidth={1.8} />
        </motion.div>

        <h1 className="bg-gradient-to-r from-brand-700 via-brand-500 to-sun-500 bg-clip-text text-6xl font-black tracking-tight text-transparent sm:text-7xl">
          UdaanHer
          <span className="block text-4xl font-bold sm:text-5xl">Saathi</span>
        </h1>

        <p className="max-w-md text-2xl font-semibold text-brand-800">बोलिए · सीखिए · कमाइए</p>
        <p className="max-w-sm text-lg text-muted-foreground">
          Your voice didi for learning skills that earn
        </p>
      </motion.div>

      <motion.div variants={item} className="flex w-full max-w-sm flex-col gap-4">
        <p className="text-base font-medium text-muted-foreground">
          अपनी भाषा चुनिए · તમારી ભાષા પસંદ કરો
        </p>
        {LANGUAGES.map((lang) => {
          const isThisOne = connectingLanguage === lang.code;
          return (
            <motion.button
              key={lang.code}
              type="button"
              disabled={connecting}
              onClick={() => onPick(lang.code)}
              className={cn(
                'flex min-h-20 items-center justify-between rounded-2xl border-2 border-brand-200 bg-white/80 px-8 shadow-lg shadow-brand-200/40 backdrop-blur transition-colors',
                'hover:border-brand-400 hover:bg-white',
                connecting && !isThisOne && 'opacity-40',
                isThisOne && 'border-brand-500 bg-white',
              )}
              whileHover={connecting ? undefined : { scale: 1.03 }}
              whileTap={connecting ? undefined : { scale: 0.97 }}
            >
              <span className="text-3xl font-bold text-brand-900">{lang.label}</span>
              {isThisOne ? (
                <Loader2 className="size-7 animate-spin text-brand-500" />
              ) : (
                <span className="text-sm font-medium text-muted-foreground">{lang.sub}</span>
              )}
            </motion.button>
          );
        })}
        {connecting && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-base text-muted-foreground"
          >
            आपकी दीदी आ रही हैं…
          </motion.p>
        )}
      </motion.div>
    </motion.div>
  );
}
