import type { ShowLessonStepCommand } from '../types';

interface Props {
  step: ShowLessonStepCommand;
}

export function LessonStep({ step }: Props) {
  return (
    <div className="lesson-step">
      {step.image && <img src={step.image} alt="" className="lesson-step__image" />}
      <p className="lesson-step__caption">{step.caption}</p>
      <div className="lesson-step__dots">
        {Array.from({ length: step.total_steps }).map((_, i) => (
          <span
            key={i}
            className={`lesson-step__dot ${i === step.step_index ? 'lesson-step__dot--active' : ''}`}
          />
        ))}
      </div>
    </div>
  );
}
