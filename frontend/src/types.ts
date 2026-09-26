// Language expansion (roadmap item 7): Bengali is the first of the
// ordered list (Bengali, Kannada, Malayalam, Marathi, Odia, Tamil, Telugu)
// to land -- content translations are AI drafts pending native-speaker
// review before this is considered launched (see TODO.md item 7).
export type SessionLanguage = 'gu-IN' | 'hi-IN' | 'pa-IN' | 'bn-IN' | 'en-IN';

export interface OptionCardData {
  id: string;
  label: string;
  /** Absent for text-only cards, e.g. the language choices. */
  image?: string | null;
}

export interface IdleCommand {
  type: 'idle';
}

export interface RequestPhotoCommand {
  type: 'request_photo';
  prompt: string;
}

export interface RequestPinCommand {
  type: 'request_pin';
  prompt: string;
  attempt: number;
  max_attempts: number;
}

export interface ShowOptionsCommand {
  type: 'show_options';
  prompt: string;
  options: OptionCardData[];
}

export interface ShowLessonStepCommand {
  type: 'show_lesson_step';
  lesson_id: string;
  step_index: number;
  total_steps: number;
  // Optional (plan v2): voice is the interface; a step's visual is an aid,
  // not a requirement. null renders as a caption-only card.
  image: string | null;
  caption: string;
}

export interface ShowVideoCommand {
  type: 'show_video';
  url: string;
  caption: string;
}

export interface LearnerProfile {
  name: string;
  village: string;
  language: string;
  interest: string;
  starting_level: 'new' | 'some' | 'experienced';
  notes: string;
  /** Present only on the card shown right after her profile is saved: her 4-digit return PIN. */
  pin?: string | null;
}

export interface ShowProfileCardCommand {
  type: 'show_profile_card';
  profile: LearnerProfile;
}

export interface ProgressLesson {
  lesson_id: string;
  title: string;
  status: 'done' | 'current' | 'locked';
}

export interface ProgressConcept {
  concept_id: string;
  label: string;
  mastery: 'strong' | 'shaky' | 'unseen';
}

export interface ProgressPayload {
  skill: string;
  lessons: ProgressLesson[];
  concepts: ProgressConcept[];
  next_step_text: string;
}

export interface JourneyMilestone {
  milestone_id: string;
  label_hi: string;
  label_en: string;
  achieved: boolean;
  auto_tracked: boolean;
}

export interface JourneyPayload {
  skill_id: string;
  milestones: JourneyMilestone[];
  next_step_text: string;
}

export interface ShowProgressCommand {
  type: 'show_progress';
  payload: ProgressPayload;
}

export type UICommand =
  | IdleCommand
  | ShowOptionsCommand
  | ShowLessonStepCommand
  | ShowVideoCommand
  | ShowProfileCardCommand
  | ShowProgressCommand
  | RequestPhotoCommand
  | RequestPinCommand;
