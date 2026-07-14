import { motion } from 'motion/react';
import type { OptionCardData } from '../types';

interface Props {
  prompt: string;
  options: OptionCardData[];
  onTap: (id: string) => void;
}

export function OptionCards({ prompt, options, onTap }: Props) {
  return (
    <div className="flex w-full max-w-2xl flex-col items-center gap-6">
      <p className="text-center text-2xl font-semibold text-brand-900 sm:text-3xl">{prompt}</p>
      <div className="grid w-full grid-cols-2 gap-4 sm:gap-5">
        {options.map((option, i) => (
          <motion.button
            key={option.id}
            type="button"
            onClick={() => onTap(option.id)}
            className="flex flex-col items-center gap-3 rounded-3xl border-2 border-brand-100 bg-white/85 p-5 shadow-lg shadow-brand-200/40 backdrop-blur hover:border-brand-400"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08, type: 'spring', stiffness: 150, damping: 18 }}
            whileHover={{ scale: 1.04 }}
            whileTap={{ scale: 0.95 }}
          >
            {option.image && (
              <img
                src={option.image}
                alt=""
                className="aspect-square w-full max-w-40 rounded-2xl object-cover"
              />
            )}
            <span className="text-xl font-bold text-brand-900 sm:text-2xl">{option.label}</span>
          </motion.button>
        ))}
      </div>
    </div>
  );
}
