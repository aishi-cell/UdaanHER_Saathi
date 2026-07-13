import { motion } from 'motion/react';
import { MapPin, Sparkles } from 'lucide-react';
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
          className="flex size-24 items-center justify-center rounded-full bg-gradient-to-br from-brand-400 to-sun-400 text-5xl font-black text-white shadow-lg"
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
      </CardContent>
    </Card>
  );
}
