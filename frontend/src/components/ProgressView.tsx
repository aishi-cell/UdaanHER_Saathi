import type { ProgressPayload } from '../types';

interface Props {
  payload: ProgressPayload;
}

const MASTERY_COLOR: Record<ProgressPayload['concepts'][number]['mastery'], string> = {
  strong: '#2f8f5b',
  shaky: '#d69a2d',
  unseen: '#999999',
};

const LESSON_STATUS_LABEL: Record<ProgressPayload['lessons'][number]['status'], string> = {
  done: '✓',
  current: '→',
  locked: '🔒',
};

export function ProgressView({ payload }: Props) {
  return (
    <div className="progress-view">
      <ul className="progress-view__lessons">
        {payload.lessons.map((lesson) => (
          <li key={lesson.lesson_id}>
            <span>{LESSON_STATUS_LABEL[lesson.status]}</span> {lesson.title}
          </li>
        ))}
      </ul>
      <div className="progress-view__concepts">
        {payload.concepts.map((concept) => (
          <span
            key={concept.concept_id}
            className="progress-view__chip"
            style={{ backgroundColor: MASTERY_COLOR[concept.mastery] }}
          >
            {concept.label}
          </span>
        ))}
      </div>
      <p className="progress-view__next">{payload.next_step_text}</p>
    </div>
  );
}
