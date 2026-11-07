import { useEffect, useRef, type ReactNode } from "react";
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
  const sheetRef = useRef<HTMLDivElement | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    returnFocus.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    return () => {
      const target = returnFocus.current;
      if (
        target &&
        target.isConnected &&
        (document.activeElement == null ||
          document.activeElement === document.body ||
          sheetRef.current?.contains(document.activeElement))
      ) {
        target.focus({ preventScroll: true });
      }
    };
  }, []);

  useEffect(() => {
    if (!top) return;
    const sheet = sheetRef.current;
    const focusableElements = () =>
      Array.from(
        sheet?.querySelectorAll<HTMLElement>(
          "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
        ) ?? [],
      ).filter(
        (element) =>
          element.offsetParent !== null &&
          getComputedStyle(element).visibility !== "hidden",
      );
    const focusFirst = () => {
      const first = focusableElements()[0];
      (first ?? sheet)?.focus({ preventScroll: true });
    };
    if (!sheet?.contains(document.activeElement)) focusFirst();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !sheet) return;
      const focusable = focusableElements();
      if (focusable.length === 0) {
        event.preventDefault();
        sheet.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
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
        ref={sheetRef}
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
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
