import type { UICommand } from '../types';
import { OptionCards } from './OptionCards';
import { LessonStep } from './LessonStep';
import { VideoEmbed } from './VideoEmbed';
import { ProfileCard } from './ProfileCard';
import { ProgressView } from './ProgressView';
import { PhotoRequest } from './PhotoRequest';

interface Props {
  ui: UICommand;
  onTapOption: (id: string) => void;
  onPhoto: (file: File) => void;
}

export function Renderer({ ui, onTapOption, onPhoto }: Props) {
  switch (ui.type) {
    case 'idle':
      return null;
    case 'show_options':
      return <OptionCards prompt={ui.prompt} options={ui.options} onTap={onTapOption} />;
    case 'show_lesson_step':
      return <LessonStep step={ui} />;
    case 'show_video':
      return <VideoEmbed video={ui} />;
    case 'show_profile_card':
      return <ProfileCard profile={ui.profile} />;
    case 'show_progress':
      return <ProgressView payload={ui.payload} />;
    case 'request_photo':
      return <PhotoRequest prompt={ui.prompt} onPhoto={onPhoto} />;
  }
}
