import { isDemoRecovery } from "../demo";
import { isPreview } from "../variant";

/** Der Ring neben dem Namen; in der Vorschau offen und im Akzent. */
export function BrandMark({ large = false }: { large?: boolean }) {
  const classes = ["brand-mark", large ? "large" : "", isPreview ? "preview" : ""]
    .filter(Boolean)
    .join(" ");

  return <span className={classes} aria-hidden="true" />;
}

/** Die Plakette, die die Vorschau von der fertigen Version unterscheidet. */
export function PreviewTag() {
  return isPreview ? <span className="brand-tag">Vorschau</span> : null;
}

/** Der Demo-Zustand trägt sein eigenes, deutlich abweichendes Abzeichen. */
export function DemoTag() {
  return isDemoRecovery ? (
    <span className="brand-tag demo" aria-label="Demo-Zustand">
      Demo
    </span>
  ) : null;
}
