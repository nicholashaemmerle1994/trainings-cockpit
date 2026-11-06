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

/** Eine Zeile „Label links, Wert rechts" — reine Information, keine Aktion. */
export function MetricRow({
  label,
  value,
  compact = false,
  className,
}: {
  label: string;
  value: ReactNode;
  compact?: boolean;
  className?: string;
}) {
  const classes = [
    "metric-row",
    compact ? "metric-row--compact" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes}>
      <span className="metric-row__label">{label}</span>
      <span className="metric-row__value">{value}</span>
    </div>
  );
}

export type BadgeTone =
  | "neutral"
  | "positive"
  | "warning"
  | "negative"
  | "band-top"
  | "band-good"
  | "band-mid"
  | "band-low"
  | "band-bad";

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
