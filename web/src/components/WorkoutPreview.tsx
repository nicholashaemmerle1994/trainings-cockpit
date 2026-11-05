import type { ReactNode } from "react";
import { sportIcon } from "./sportIcon";

/** Eine klickbare Einheit in Training und Wochenblatt — überall dieselbe Zeile. */
export function WorkoutPreview({
  sport,
  name,
  meta,
  trailing,
  onClick,
}: {
  sport: string;
  name: string;
  meta: string;
  trailing?: ReactNode;
  onClick: () => void;
}) {
  const Icon = sportIcon(sport);
  return (
    <button type="button" className="train-row" onClick={onClick}>
      <span className="train-ico">
        <Icon size={18} />
      </span>
      <span className="train-main">
        <span className="train-name">{name}</span>
        <span className="train-meta">{meta}</span>
      </span>
      {trailing}
    </button>
  );
}
