import { useState } from "react";
import { fmtDateLong } from "../format";
import { Sheet } from "./Sheet";

export type StartTemplate = "simple" | "repeat" | "empty";

export interface NewPlanConfig {
  draftId: string;
  sport: string;
  date: string;
  name: string;
  template: StartTemplate;
}

const SPORTS = [
  { value: "Run", label: "Laufen" },
  { value: "Ride", label: "Radfahren" },
  { value: "Swim", label: "Schwimmen" },
];

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

/**
 * Anlegeablauf vom Tages-Plus zum lokalen Entwurf.
 *
 * Die Sportart ist ausschließlich ein Text-Dropdown. „Weiter“ erzeugt nur
 * einen lokalen Entwurf; ein Event wird erst beim späteren Speichern angelegt.
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

  return (
    <Sheet crumb="Neue Einheit" label="Neue Einheit" onClose={onClose}>
      <p className="add-workout__eyebrow">Neue Einheit</p>
      <h1 className="add-workout__title">Was steht an?</h1>
      <p className="add-workout__date">{fmtDateLong(day)}</p>

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
    </Sheet>
  );
}
