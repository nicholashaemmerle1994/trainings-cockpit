import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { IconBack, IconClose } from "./icons";

/**
 * Der gemeinsame Rahmen für alles, was über der Seite liegt.
 *
 * Ein Portal ans Ende des Dokuments: `.page` trägt eine Eintritts-Animation und
 * damit einen eigenen Stapelkontext — darin läge das Blatt unter der Tableiste
 * und wäre an die Seite statt an das Fenster gebunden.
 */
export function Sheet({
  crumb,
  label,
  onClose,
  top = true,
  children,
}: {
  crumb: string;
  label: string;
  onClose: () => void;
  /** Liegt ein zweites Blatt darüber, schließt Escape nur dieses. */
  top?: boolean;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!top) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, top]);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  return createPortal(
    <div className="sheet-backdrop" onClick={onClose} role="presentation">
      <div
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-label={label}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="sheet-top">
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Zurück">
            <IconBack size={18} />
          </button>
          <span className="sheet-crumb">{crumb}</span>
          <button
            type="button"
            className="icon-btn sheet-close"
            onClick={onClose}
            aria-label="Schließen"
          >
            <IconClose size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}
