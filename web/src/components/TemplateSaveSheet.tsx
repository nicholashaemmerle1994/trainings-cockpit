import { useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { TemplateDetail } from "../types";
import { Sheet } from "./Sheet";

const NAME_MAX = 120;

function validateName(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return "Die Vorlage braucht einen Namen.";
  if (trimmed.length > NAME_MAX) {
    return `Der Vorlagenname darf höchstens ${NAME_MAX} Zeichen haben.`;
  }
  if (/[\n\r\t]/.test(trimmed)) {
    return "Der Vorlagenname darf keine Zeilenumbrüche oder Tabulatoren enthalten.";
  }
  return null;
}

function saveError(cause: unknown): string {
  if (cause instanceof ApiError) {
    if (cause.cloneCode === "serialization_failed") {
      return "Der Aufbau lässt sich nicht sicher speichern. Ein Schrittname mit Maßangabe oder ein nicht unterstützter Inhalt blockiert den vorhandenen Speicherweg; es wird nichts gekürzt.";
    }
    if (cause.cloneCode === "notes") {
      return "Diese Planung enthält Notizen. Sie lassen sich nicht verlustfrei in eine Vorlage übernehmen.";
    }
    if (cause.cloneCode === "open_end" || cause.cloneCode === "empty_structure") {
      return "Der Aufbau ist unvollständig und lässt sich nicht als Vorlage speichern.";
    }
    return cause.message;
  }
  return cause instanceof Error
    ? cause.message
    : "Die Vorlage konnte nicht gespeichert werden.";
}

/**
 * Kleines Blatt zum Speichern des **persistierten** Plans als lokale Vorlage.
 *
 * Es wird ausschließlich die vorhandene Event-Zeile gelesen. Ein laufender
 * lokaler Entwurf ist bewusst nicht Teil dieses Vorgangs.
 */
export function TemplateSaveSheet({
  eventId,
  defaultName,
  sportLabel,
  knownText,
  onClose,
  onSaved,
}: {
  eventId: number;
  defaultName: string;
  sportLabel: string;
  knownText: string;
  onClose: () => void;
  onSaved?: (template: TemplateDetail) => void;
}) {
  const [name, setName] = useState(defaultName);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<TemplateDetail | null>(null);
  const savingRef = useRef(false);

  const localError = success ? null : validateName(name);

  const save = async () => {
    if (savingRef.current || success) return;
    const message = validateName(name);
    if (message) {
      setError(message);
      return;
    }
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      const template = await api.saveTemplateFromPlan(eventId, name.trim());
      setSuccess(template);
      onSaved?.(template);
    } catch (cause: unknown) {
      setError(saveError(cause));
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  return (
    <Sheet crumb="Als Vorlage speichern" label="Als Vorlage speichern" onClose={onClose}>
      <p className="add-workout__eyebrow">Lokale Vorlage</p>
      <h1 className="add-workout__title">Als Vorlage speichern</h1>
      <p className="sheet-kind">
        {sportLabel} · {knownText}
      </p>
      <p className="template-save__source">
        Übernommen wird der gespeicherte Stand dieser Planung — nicht ein
        laufender, ungespeicherter Entwurf.
      </p>

      {success ? (
        <section className="template-save__success" role="status">
          <h2>Vorlage „{success.name}“ gespeichert</h2>
          <p>
            Sie steht jetzt beim Tages-Plus unter „Aus Vorlage erstellen“ bereit.
            Es wurde kein Training an intervals.icu gesendet.
          </p>
          <button type="button" className="btn btn--primary" onClick={onClose}>
            Fertig
          </button>
        </section>
      ) : (
        <form
          className="template-save"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <div className="plan-field">
            <label htmlFor="template-save-name">Name der Vorlage</label>
            <input
              id="template-save-name"
              className="plan-input"
              type="text"
              maxLength={NAME_MAX}
              value={name}
              autoFocus
              disabled={saving}
              onChange={(event) => {
                setName(event.target.value);
                setError(null);
              }}
            />
          </div>
          <p className="plan-note plan-note--muted">
            Sportart und vollständiger Aufbau werden automatisch übernommen.
            Notizen werden nicht Teil der Vorlage.
          </p>
          {localError && name.length > 0 && (
            <p className="template-save__error" role="alert">
              {localError}
            </p>
          )}
          {error && (
            <p className="template-save__error" role="alert">
              {error}
            </p>
          )}
          <div className="template-save__actions">
            <button
              type="button"
              className="btn btn--ghost"
              onClick={onClose}
              disabled={saving}
            >
              Abbrechen
            </button>
            <button
              type="submit"
              className="btn btn--primary"
              disabled={saving || localError != null}
            >
              {saving ? "Wird gespeichert…" : "Vorlage speichern"}
            </button>
          </div>
        </form>
      )}
    </Sheet>
  );
}
