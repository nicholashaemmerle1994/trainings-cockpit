import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { fmtDateLong, fmtKm, fmtSpan } from "../format";
import type { PlanNode, TemplateSummary } from "../types";
import { Sheet } from "./Sheet";

export type StartTemplate = "simple" | "repeat" | "empty";

export interface NewPlanConfig {
  draftId: string;
  sport: string;
  date: string;
  name: string;
  template: StartTemplate;
  /** Aufbau aus einer Vorlagenprojektion; nur lokal, ohne Event-Create. */
  nodes?: PlanNode[];
}

const SPORTS = [
  { value: "Run", label: "Laufen" },
  { value: "Ride", label: "Radfahren" },
  { value: "Swim", label: "Schwimmen" },
];

const SPORT_LABELS: Record<string, string> = {
  Run: "Laufen",
  Ride: "Radfahren",
  Swim: "Schwimmen",
};

const TEMPLATES: {
  value: StartTemplate;
  title: string;
  hint: string;
}[] = [
  {
    value: "simple",
    title: "Einfacher Abschnitt",
    hint: "Zum Beispiel ein durchgehender Z2-Lauf.",
  },
  {
    value: "repeat",
    title: "Mit Wiederholungen",
    hint: "Ein Startpunkt für Belastung und Erholung.",
  },
  {
    value: "empty",
    title: "Leer beginnen",
    hint: "Den Aufbau selbst zusammenstellen.",
  },
];

function newDraftId(): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `draft:new:${random}`;
}

function templateMeta(template: TemplateSummary): string {
  const parts = [SPORT_LABELS[template.sport] ?? template.sport];
  if (template.known_seconds != null && template.known_seconds > 0) {
    parts.push(fmtSpan(template.known_seconds));
  }
  if (template.known_metres != null && template.known_metres > 0) {
    parts.push(fmtKm(template.known_metres / 1000));
  }
  if (template.executions != null && template.executions > 0) {
    parts.push(
      `${template.executions} ${template.executions === 1 ? "Abschnitt" : "Abschnitte"}`,
    );
  }
  if (template.has_unknown) parts.push("Angaben unvollständig");
  return parts.join(" · ");
}

function templateError(cause: unknown): string {
  if (cause instanceof ApiError) {
    if (cause.code === "serialization_failed") {
      return "Diese Vorlage lässt sich nicht sicher neu anlegen. Der Aufbau enthält einen Abschnitt, den der bestehende Speicherweg nicht schreiben kann.";
    }
    return cause.message;
  }
  return cause instanceof Error
    ? cause.message
    : "Die Vorlage konnte nicht übernommen werden.";
}

/**
 * Anlegeablauf vom Tages-Plus zum lokalen Entwurf.
 *
 * Die Sportart ist ausschließlich ein Text-Dropdown. „Weiter“ erzeugt nur
 * einen lokalen Entwurf; ein Event wird erst beim späteren Speichern angelegt.
 * Die Vorlagenprojektion ist ebenfalls rein lokal: Sie liefert neue Knoten-IDs
 * und wird als vollständiger Aufbau in den vorhandenen Entwurf übergeben.
 */
export function AddWorkoutSheet({
  day,
  onContinue,
  onClose,
}: {
  day: string;
  onContinue: (config: NewPlanConfig) => void;
  onClose: () => void;
}) {
  const [sport, setSport] = useState("Run");
  const [name, setName] = useState("");
  const [template, setTemplate] = useState<StartTemplate>("simple");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [templates, setTemplates] = useState<TemplateSummary[] | null>(null);
  const [templateErrorText, setTemplateErrorText] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [projecting, setProjecting] = useState<string | null>(null);
  const [projectError, setProjectError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const loadTemplates = () => {
    setTemplateErrorText(null);
    setTemplates(null);
    api
      .templates()
      .then((result) => {
        if (mounted.current) setTemplates(result.items);
      })
      .catch((cause: unknown) => {
        if (!mounted.current) return;
        setTemplates([]);
        setTemplateErrorText(
          cause instanceof Error
            ? cause.message
            : "Die Vorlagen konnten nicht geladen werden.",
        );
      });
  };

  const openPicker = () => {
    setPickerOpen(true);
    setProjectError(null);
    setSearch("");
    loadTemplates();
  };

  const useTemplate = async (summary: TemplateSummary) => {
    if (!summary.available || projecting !== null) return;
    const draftId = newDraftId();
    setProjecting(summary.template_id);
    setProjectError(null);
    try {
      const projection = await api.projectTemplate(
        summary.template_id,
        day,
        draftId,
      );
      if (!mounted.current) return;
      onContinue({
        draftId,
        sport: projection.sport,
        date: day,
        name: projection.name || summary.name,
        template: "empty",
        nodes: projection.nodes,
      });
    } catch (cause: unknown) {
      if (mounted.current) setProjectError(templateError(cause));
    } finally {
      if (mounted.current) setProjecting(null);
    }
  };

  const needle = search.trim().toLocaleLowerCase("de");
  const filtered = (templates ?? []).filter((item) => {
    if (!needle) return true;
    return (
      item.name.toLocaleLowerCase("de").includes(needle) ||
      (SPORT_LABELS[item.sport] ?? item.sport)
        .toLocaleLowerCase("de")
        .includes(needle)
    );
  });

  return (
    <Sheet crumb="Neue Einheit" label="Neue Einheit" onClose={onClose}>
      <p className="add-workout__eyebrow">Neue Einheit</p>
      <h1 className="add-workout__title">Was steht an?</h1>
      <p className="add-workout__date">{fmtDateLong(day)}</p>

      {!pickerOpen ? (
        <>
          <button
            type="button"
            className="add-workout__from-template"
            onClick={openPicker}
          >
            <span aria-hidden="true">◇</span>
            Aus Vorlage erstellen
          </button>

          <form
            className="add-workout"
            onSubmit={(event) => {
              event.preventDefault();
              onContinue({
                draftId: newDraftId(),
                sport,
                date: day,
                name: name.trim(),
                template,
              });
            }}
          >
            <div className="plan-field">
              <label htmlFor="add-workout-sport">Sportart</label>
              <select
                id="add-workout-sport"
                className="plan-input"
                value={sport}
                onChange={(event) => setSport(event.target.value)}
              >
                {SPORTS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="plan-field">
              <label htmlFor="add-workout-name">Name · optional</label>
              <input
                id="add-workout-name"
                className="plan-input"
                type="text"
                value={name}
                placeholder="Name der Einheit"
                onChange={(event) => setName(event.target.value)}
              />
            </div>

            <fieldset className="add-workout__templates">
              <legend>Aufbau</legend>
              {TEMPLATES.map((option) => (
                <label
                  key={option.value}
                  className={`add-workout__option${
                    template === option.value ? " add-workout__option--selected" : ""
                  }`}
                >
                  <input
                    type="radio"
                    name="add-workout-template"
                    value={option.value}
                    checked={template === option.value}
                    onChange={() => setTemplate(option.value)}
                  />
                  <span className="add-workout__radio" aria-hidden="true" />
                  <span className="add-workout__option-text">
                    <strong>{option.title}</strong>
                    <span>{option.hint}</span>
                  </span>
                </label>
              ))}
            </fieldset>

            <div className="add-workout__footer">
              <p>Datum ist bereits übernommen.</p>
              <button type="submit" className="btn btn--primary">
                Weiter →
              </button>
            </div>
          </form>
        </>
      ) : (
        <section className="template-picker" aria-labelledby="template-picker-title">
          <div className="template-picker__head">
            <div>
              <h2 id="template-picker-title">Aus Vorlage erstellen</h2>
              <p>Der Aufbau wird als neuer lokaler Entwurf übernommen.</p>
            </div>
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setPickerOpen(false)}
              disabled={projecting !== null}
            >
              Zurück
            </button>
          </div>

          <div className="plan-field">
            <label htmlFor="template-search">Suchen · optional</label>
            <input
              id="template-search"
              className="plan-input"
              type="search"
              value={search}
              placeholder="Vorlagenname oder Sportart"
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>

          {projectError && (
            <p className="template-picker__error" role="alert">
              {projectError}
            </p>
          )}
          {templateErrorText && (
            <div className="template-picker__error" role="alert">
              <p>{templateErrorText}</p>
              <button type="button" className="btn btn--ghost" onClick={loadTemplates}>
                Erneut laden
              </button>
            </div>
          )}
          {templates == null && (
            <div className="template-picker__loading" role="status">
              Vorlagen werden geladen…
            </div>
          )}
          {templates != null && templates.length === 0 && !templateErrorText && (
            <p className="template-picker__empty">
              Noch keine Vorlagen. Öffne eine geplante Einheit und wähle „Als
              Vorlage speichern“.
            </p>
          )}
          {templates != null && templates.length > 0 && filtered.length === 0 && (
            <p className="template-picker__empty">
              Keine Vorlage passt zu „{search.trim()}“.
            </p>
          )}

          <ul className="template-picker__list">
            {filtered.map((item) => (
              <li key={item.template_id}>
                <button
                  type="button"
                  className="template-picker__item"
                  disabled={!item.available || projecting !== null}
                  onClick={() => void useTemplate(item)}
                  aria-label={`${item.name} als neuen Entwurf verwenden`}
                >
                  <span className="template-picker__main">
                    <strong>{item.name}</strong>
                    <span>{templateMeta(item)}</span>
                    {!item.available && (
                      <span className="template-picker__unavailable">
                        {item.error_code === "corrupt"
                          ? "Diese Vorlage ist beschädigt und kann nicht verwendet werden."
                          : "Diese Vorlage ist derzeit nicht verfügbar."}
                      </span>
                    )}
                  </span>
                  <span className="template-picker__side">
                    {projecting === item.template_id ? (
                      "Wird übernommen…"
                    ) : (
                      <span aria-hidden="true">›</span>
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </Sheet>
  );
}
