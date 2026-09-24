import { Card, CardContent } from '@/components/ui/card';
import { Keypad } from './Keypad';
import type { RequestPinCommand } from '../types';

interface Props {
  ui: RequestPinCommand;
  onSubmit: (pin: string) => void;
}

/** The keypad shown alongside Saathi's voice ask for a returning learner's
 * PIN -- available from the first attempt, not only once voice has failed
 * (login roadmap item 1). Tapping submits exactly like speaking would. */
export function RequestPin({ ui, onSubmit }: Props) {
  const triesLeft = ui.max_attempts - ui.attempt + 1;
  return (
    <Card className="w-full max-w-md border-brand-100 bg-white/85 shadow-xl shadow-brand-200/40 backdrop-blur">
      <CardContent className="flex flex-col items-center gap-5 p-7 text-center">
        <p className="text-lg font-medium leading-relaxed text-foreground">{ui.prompt}</p>
        <Keypad onSubmit={onSubmit} />
        <p className="text-sm text-muted-foreground">
          बोलकर भी बता सकती हैं · Or just say it — {triesLeft} tries left
        </p>
      </CardContent>
    </Card>
  );
}
