export interface OptionCardData {
  id: string;
  label: string;
  image: string;
}

export interface IdleCommand {
  type: 'idle';
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
  | ShowProgressCommand;
