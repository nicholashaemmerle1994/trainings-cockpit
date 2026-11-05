import type { ReactNode } from "react";

type CardTag = "section" | "article" | "aside";

/** Die Karte des Designsystems: Fläche, Kopf und ein Kindbereich. */
export function DashboardCard({
  as = "section",
  title,
  subtitle,
  action,
  children,
  className,
}: {
  as?: CardTag;
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const Tag = as;
  return (
    <Tag className={["card", className].filter(Boolean).join(" ")}>
      {(title || action) && (
        <div className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p className="card-sub">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </Tag>
  );
}

/** Eine Zeile „Label links, Wert rechts" — als Text oder als ganze Schaltfläche. */
export function MetricRow({
  label,
  value,
  onClick,
  compact = false,
  className,
}: {
  label: string;
  value: ReactNode;
  onClick?: () => void;
  compact?: boolean;
  className?: string;
}) {
  const classes = [
    "metric-row",
    compact ? "metric-row--compact" : "",
    onClick ? "metric-row--button" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  const content = (
    <>
      <span className="metric-row__label">{label}</span>
      <span className="metric-row__value">
        {value}
        {onClick && (
          <span className="metric-row__caret" aria-hidden="true">
            ›
          </span>
        )}
      </span>
    </>
  );

  if (onClick) {
    return (
      <button type="button" className={classes} onClick={onClick}>
        {content}
      </button>
    );
  }

  return <div className={classes}>{content}</div>;
}

export type BadgeTone = "neutral" | "positive" | "warning" | "negative" | "accent";

/** Ein kleiner Statuschip; die Farbe sagt dasselbe wie der Text. */
export function StatusBadge({
  tone = "neutral",
  children,
}: {
  tone?: BadgeTone;
  children: ReactNode;
}) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function Skeleton({ height = 120 }: { height?: number }) {
  return <div className="skeleton" style={{ height }} />;
}

export function EmptyState({
  title,
  text,
  action,
}: {
  title: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-mark" />
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
