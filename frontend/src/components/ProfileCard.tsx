import { motion } from 'motion/react';
import { KeyRound, MapPin, Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import type { LearnerProfile } from '../types';

interface Props {
  profile: LearnerProfile;
}

const LEVEL_LABEL: Record<LearnerProfile['starting_level'], string> = {
  new: 'नई शुरुआत',
  some: 'थोड़ा अनुभव',
  experienced: 'अनुभवी',
};

export function ProfileCard({ profile }: Props) {
  return (
    <Card className="w-full max-w-md border-brand-100 bg-white/85 shadow-xl shadow-brand-200/40 backdrop-blur">
      <CardContent className="flex flex-col items-center gap-4 p-7 text-center sm:p-8">
        <motion.div
          className="flex size-24 items-center justify-center rounded-full bg-gradient-to-br from-brand-400 to-blush-400 text-5xl font-black text-white shadow-lg"
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 200, damping: 15 }}
        >
          {profile.name.charAt(0).toUpperCase() || '?'}
        </motion.div>

        <p className="text-4xl font-bold text-brand-900">{profile.name}</p>

        <div className="flex flex-wrap items-center justify-center gap-2">
          {profile.village && (
            <Badge variant="secondary" className="gap-1.5 px-3 py-1.5 text-base font-medium">
              <MapPin className="size-4" /> {profile.village}
            </Badge>
          )}
          <Badge variant="secondary" className="gap-1.5 px-3 py-1.5 text-base font-medium">
            <Sparkles className="size-4" /> {profile.interest}
          </Badge>
          <Badge className="bg-accent px-3 py-1.5 text-base font-medium text-accent-foreground">
            {LEVEL_LABEL[profile.starting_level]}
          </Badge>
        </div>

        {profile.notes && (
          <p className="max-w-sm text-base leading-relaxed text-muted-foreground">
            {profile.notes}
          </p>
        )}

        {profile.pin && (
          <motion.div
            className="flex flex-col items-center gap-2 rounded-2xl bg-brand-50 px-6 py-4"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <span className="flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wide text-brand-700">
              <KeyRound className="size-4" /> आपका PIN · Your PIN
            </span>
            <span className="text-4xl font-black tracking-[0.4em] text-brand-900">
              {profile.pin}
            </span>
            <span className="text-sm text-muted-foreground">
              अगली बार नाम और PIN बोलिए · Say your name + PIN next time
            </span>
          </motion.div>
        )}
      </CardContent>
    </Card>
  );
}
