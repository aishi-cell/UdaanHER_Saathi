import { Card, CardContent } from '@/components/ui/card';
import type { ShowVideoCommand } from '../types';

interface Props {
  video: ShowVideoCommand;
}

export function VideoEmbed({ video }: Props) {
  return (
    <Card className="w-full max-w-2xl border-brand-100 bg-white/85 shadow-xl shadow-brand-200/40 backdrop-blur">
      <CardContent className="flex flex-col gap-4 p-5 sm:p-6">
        <p className="text-center text-lg font-semibold text-brand-800">
          Here's a quick view to help you
        </p>
        <div className="aspect-video w-full overflow-hidden rounded-2xl bg-black">
          <iframe
            src={video.url}
            title={video.caption}
            className="size-full"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
          />
        </div>
        <p className="text-center text-xl font-semibold text-brand-900 sm:text-2xl">
          {video.caption}
        </p>
      </CardContent>
    </Card>
  );
}
