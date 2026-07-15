import { useRef } from 'react';
import { motion } from 'motion/react';
import { Camera } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

interface Props {
  prompt: string;
  onPhoto: (file: File) => void;
}

/** Practice review: one big camera button; the photo goes straight to the
 * mentor for warm feedback. Voice keeps working alongside (she can also
 * just say she's done or wants to skip). */
export function PhotoRequest({ prompt, onPhoto }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <Card className="w-full max-w-md border-brand-100 bg-white/85 shadow-xl shadow-brand-200/40 backdrop-blur">
      <CardContent className="flex flex-col items-center gap-5 p-7 text-center">
        <p className="text-lg font-medium leading-relaxed text-foreground">{prompt}</p>
        <motion.button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="flex flex-col items-center gap-2 rounded-3xl bg-brand-600 px-10 py-6 text-white shadow-lg shadow-brand-400/40"
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.95 }}
        >
          <Camera className="size-12" strokeWidth={2} />
          <span className="text-lg font-bold">फोटो दिखाइए · Show a photo</span>
        </motion.button>
        <p className="text-sm text-muted-foreground">
          या बोलकर बताइए — फोटो ज़रूरी नहीं है · Or just tell me, photo is optional
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onPhoto(file);
            e.target.value = '';
          }}
        />
      </CardContent>
    </Card>
  );
}
