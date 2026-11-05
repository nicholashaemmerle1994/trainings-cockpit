import type { ReactNode } from "react";

/**
 * Der Kopf einer Seite. Das Datum ist der einzige serife Moment;
 * alle anderen Seitentitel stehen in der Systemschrift (DESIGN.md 4.1).
 */
export function ScreenHeader({
  date,
  title,
  meta,
  action,
}: {
  date?: string;
  title?: string;
  meta?: string;
  action?: ReactNode;
}) {
  return (
    <header className="screen-head">
      <div>
        {date ? (
          <h1 className="screen-head__date">{date}</h1>
        ) : (
          <h1 className="screen-head__title">{title}</h1>
        )}
        {meta && <p className="meta">{meta}</p>}
      </div>
      {action}
    </header>
  );
}
