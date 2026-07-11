import { useState } from 'react';
import { Renderer } from './components/Renderer';
import type { UICommand } from './types';
import './App.css';

function placeholderImage(label: string, color: string): string {
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><rect width='200' height='200' fill='${color}'/><text x='50%' y='50%' font-size='24' fill='white' text-anchor='middle' dominant-baseline='middle' font-family='sans-serif'>${label}</text></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

const DEMO_COMMANDS: UICommand[] = [
  { type: 'idle' },
  {
    type: 'show_options',
    prompt: 'What would you like to learn?',
    options: [
      { id: 'tailoring', label: 'Tailoring', image: placeholderImage('Tailoring', '#e8792f') },
      { id: 'beauty', label: 'Beauty', image: placeholderImage('Beauty', '#d64545') },
    ],
  },
  {
    type: 'show_lesson_step',
    lesson_id: 'tail-01-measure',
    step_index: 1,
    total_steps: 4,
    image: placeholderImage('Step 2', '#2f8f5b'),
    caption: 'Measure from shoulder to waist.',
  },
  {
    type: 'show_video',
    url: 'https://www.youtube.com/embed/dQw4w9WgXcQ',
    caption: 'How to thread a needle',
  },
  {
    type: 'show_profile_card',
    profile: {
      name: 'Sunita',
      village: 'Rampur',
      language: 'gu-IN',
      interest: 'Tailoring',
      starting_level: 'some',
      notes: 'Comfortable with basic stitches already.',
    },
  },
  {
    type: 'show_progress',
    payload: {
      skill: 'Tailoring',
      lessons: [
        { lesson_id: 'tail-01-measure', title: 'Taking Measurements', status: 'done' },
        { lesson_id: 'tail-02-cutting', title: 'Fabric Cutting', status: 'current' },
        { lesson_id: 'tail-03-stitch', title: 'Straight Stitch', status: 'locked' },
      ],
      concepts: [
        { concept_id: 'c-body-measure', label: 'Body Measurement', mastery: 'strong' },
        { concept_id: 'c-fabric-grain', label: 'Fabric Grain', mastery: 'shaky' },
      ],
      next_step_text: 'Next time: cutting practice.',
    },
  },
];

export function UiDemo() {
  const [index, setIndex] = useState(0);
  const current = DEMO_COMMANDS[index];

  return (
    <div className="kiosk">
      <section className="content-area">
        <Renderer ui={current} onTapOption={(id) => console.log('tapped', id)} />
      </section>
      <section className="talk-area">
        <p className="status-line">
          {index + 1} / {DEMO_COMMANDS.length}: {current.type}
        </p>
        <button
          type="button"
          className="talk-button talk-button--ready"
          style={{ fontSize: 24 }}
          onClick={() => setIndex((i) => (i + 1) % DEMO_COMMANDS.length)}
        >
          Next
        </button>
      </section>
    </div>
  );
}
