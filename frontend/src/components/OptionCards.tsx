import type { OptionCardData } from '../types';

interface Props {
  prompt: string;
  options: OptionCardData[];
  onTap: (id: string) => void;
}

export function OptionCards({ prompt, options, onTap }: Props) {
  return (
    <div className="option-cards">
      <p className="option-cards__prompt">{prompt}</p>
      <div className="option-cards__grid">
        {options.map((option) => (
          <button
            key={option.id}
            type="button"
            className="option-card"
            onClick={() => onTap(option.id)}
          >
            <img src={option.image} alt="" className="option-card__image" />
            <span className="option-card__label">{option.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
