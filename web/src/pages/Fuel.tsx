import { useEffect, useState } from "react";
import { api } from "../api";
import { Card } from "../components/ui";
import { fmtDuration, fmtNumber } from "../format";
import type { FuelPlan } from "../types";

const PRESETS = [45, 60, 90, 120, 180, 240, 300];

function fmtMinute(minute: number): string {
  const h = Math.floor(minute / 60);
  const m = Math.round(minute % 60);
  return `${h}:${String(m).padStart(2, "0")}`;
}

/* Auf dem iPhone hält Safari die Tastatur offen, bis das Feld den Fokus verliert.
   „Fertig" auf der Tastatur schließt sie deshalb sofort. */
function closeKeyboard(event: React.KeyboardEvent<HTMLInputElement>) {
  if (event.key === "Enter") {
    event.preventDefault();
    event.currentTarget.blur();
  }
}

export function Fuel() {
  const [mode, setMode] = useState("locker");
  const [source, setSource] = useState("gel");
  const [shot, setShot] = useState(35);
  const [unit, setUnit] = useState("g");
  const [minutes, setMinutes] = useState(120);
  const [temp, setTemp] = useState(18);
  const [weight, setWeight] = useState("");
  const [plan, setPlan] = useState<FuelPlan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const parsed = Number(weight);
    const timer = setTimeout(() => {
      api
        .fuel({
          minutes,
          mode,
          temp,
          source,
          shot,
          unit,
          weight: weight.trim() === "" || Number.isNaN(parsed) ? null : parsed,
        })
        .then((next) => {
          if (!cancelled) {
            setPlan(next);
            setError(null);
          }
        })
        .catch((err: unknown) => {
          if (!cancelled) setError(err instanceof Error ? err.message : "Fehler beim Rechnen");
        });
    }, 120);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [mode, minutes, temp, weight, source, shot, unit]);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Was du mitnimmst</h1>
          <p className="meta">Richtwerte, keine Vorschrift</p>
        </div>
      </header>

      {error && <div className="banner">{error}</div>}

      <section className="card setup">
        <div className="mode-switch">
          {(plan?.modes ?? [
            { key: "locker", label: "Locker", hint: "Long Run, Zone 2" },
            { key: "race", label: "Wettkampf", hint: "Renntempo" },
          ]).map((option) => (
            <button
              key={option.key}
              type="button"
              className={`mode-option ${mode === option.key ? "active" : ""}`}
              onClick={() => setMode(option.key)}
            >
              <strong>{option.label}</strong>
              <span>{option.hint}</span>
            </button>
          ))}
        </div>

        <div className="fuel-duration">
          <div className="field-row">
            <span className="field-label">Dauer</span>
            <span className="field-value">
              {fmtDuration(minutes)}
              <em>{plan ? `${plan.per_hour.carbs} g/h` : "—"}</em>
            </span>
          </div>
          <input
            type="range"
            min={30}
            max={360}
            step={1}
            value={minutes}
            aria-label="Dauer in Minuten"
            onChange={(event) => setMinutes(Number(event.target.value))}
          />
          <div className="chips">
            {PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                className={`chip ${minutes === preset ? "active" : ""}`}
                onClick={() => setMinutes(preset)}
              >
                {fmtDuration(preset).replace(" h", "")}
              </button>
            ))}
          </div>
        </div>

        <div className="fuel-source-col">
          <div className="fuel-source">
            <span className="field-label">Woraus</span>
            <div className="source-row">
              <div className="chips">
                {(plan?.sources ?? [
                  { key: "gel", label: "Gels & Pulver", hint: "" },
                  { key: "syrup", label: "Ahornsirup", hint: "" },
                ]).map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    className={`chip ${source === option.key ? "active" : ""}`}
                    onClick={() => setSource(option.key)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              {source === "syrup" && (
                <label className="shot-field">
                  <span className="field-label">Shot</span>
                  <input
                    type="number"
                    min={10}
                    max={250}
                    step={5}
                    inputMode="numeric"
                    enterKeyHint="done"
                    value={shot}
                    aria-label="Shotgröße"
                    onChange={(event) => setShot(Number(event.target.value))}
                    onKeyDown={closeKeyboard}
                  />
                  <span className="unit-toggle">
                    {["g", "ml"].map((option) => (
                      <button
                        key={option}
                        type="button"
                        className={unit === option ? "active" : ""}
                        onClick={() => setUnit(option)}
                      >
                        {option}
                      </button>
                    ))}
                  </span>
                </label>
              )}
            </div>
          </div>

          <div className="fuel-fields">
            <label>
              <span className="field-label">Gewicht</span>
              <input
                type="number"
                min={35}
                max={160}
                step={0.1}
                inputMode="decimal"
                enterKeyHint="done"
                placeholder={plan ? String(plan.input.weight_kg) : "78"}
                value={weight}
                aria-label="Gewicht in Kilogramm"
                onChange={(event) => setWeight(event.target.value)}
                onKeyDown={closeKeyboard}
              />
              <span className="field-hint">kg</span>
            </label>
            <label>
              <span className="field-label">Temperatur</span>
              <input
                type="number"
                min={-10}
                max={45}
                step={1}
                inputMode="numeric"
                enterKeyHint="done"
                value={temp}
                aria-label="Temperatur in Grad"
                onChange={(event) => setTemp(Number(event.target.value))}
                onKeyDown={closeKeyboard}
              />
              <span className="field-hint">°C</span>
            </label>
          </div>
        </div>
      </section>

      {plan && (
        <>
          <section className="card fuel-hero">
            <div>
              <span className="fuel-eyebrow">
                {plan.input.mode_label} · {fmtDuration(plan.input.minutes)}
              </span>
              <div className="fuel-value">
                {plan.per_hour.carbs}
                <span>g/h</span>
              </div>
              <span className="fuel-sub">
                {fmtNumber(plan.total.carbs)} g gesamt · Spanne {plan.per_hour.from}–
                {plan.per_hour.to} g/h
              </span>
            </div>

            <div className="fuel-figures">
              <div>
                <span className="fuel-figure">{fmtNumber(plan.water.ml_per_hour)}</span>
                <span className="fuel-figure-label">ml Wasser/h</span>
              </div>
              <div>
                <span className="fuel-figure">
                  {plan.sodium.salt_g_per_hour ? fmtNumber(plan.sodium.salt_g_per_hour, 1) : "—"}
                </span>
                <span className="fuel-figure-label">g Salz/h</span>
              </div>
              <div>
                <span className="fuel-figure">
                  {plan.syrup ? plan.syrup.shots : plan.gels.count || "—"}
                </span>
                <span className="fuel-figure-label">{plan.syrup ? "Shots" : "Gels"}</span>
              </div>
            </div>
          </section>

          <section className="grid-2">
            <Card title="Zeitplan" subtitle="Wann was in die Hand">
              {plan.schedule.length === 0 ? (
                <p className="note">Für diese Dauer braucht es nichts — Wasser reicht.</p>
              ) : (
                <div className="fuel-timeline">
                  {plan.schedule.map((entry, index) => (
                    <div className="fuel-row" key={`${entry.minute}-${index}`}>
                      <span className="fuel-time">{fmtMinute(entry.minute)}</span>
                      <span className="fuel-dot" data-kind={entry.kind} />
                      <div>
                        <span className="fuel-row-label">{entry.label}</span>
                        <span className="fuel-row-detail">{entry.detail}</span>
                      </div>
                      <span className="fuel-row-carbs">{entry.carbs ? `${entry.carbs} g` : ""}</span>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card title="Herrichten" subtitle="Was am Abend davor bereitsteht">
              <div className="prep">
                {!plan.syrup && (
                  <div className="prep-row">
                    <span className="prep-key">Getränk</span>
                    <span className="prep-val">
                      {plan.drink.carbs_per_bottle
                        ? `${plan.drink.bottles} × ${plan.drink.bottle_ml} ml mit je ${plan.drink.carbs_per_bottle} g`
                        : "Wasser"}
                    </span>
                    <span className="prep-note">
                      {plan.drink.carbs_per_bottle
                        ? `${fmtNumber(plan.drink.concentration_pct, 1)} % — ${fmtNumber(
                            plan.drink.carbs_per_hour,
                          )} g/h kommen aus dem Getränk`
                        : "Kein Pulver nötig"}
                    </span>
                  </div>
                )}

                {plan.syrup && plan.syrup.shots > 0 ? (
                  <div className="prep-row">
                    <span className="prep-key">Ahornsirup</span>
                    <span className="prep-val">{fmtNumber(plan.syrup.ml_total)} ml</span>
                    <span className="prep-note">
                      {plan.syrup.shots} Shots à {plan.syrup.amount} {plan.syrup.unit} ·{" "}
                      {fmtNumber(plan.syrup.carbs_per_shot)} g pro Shot, zusammen{" "}
                      {fmtNumber(plan.syrup.carbs_total)} g · alle {plan.syrup.minutes_between} min
                    </span>
                  </div>
                ) : (
                  <div className="prep-row">
                    <span className="prep-key">Gels</span>
                    <span className="prep-val">
                      {plan.gels.count ? `${plan.gels.count} Stück` : "—"}
                    </span>
                    <span className="prep-note">
                      {plan.gels.count
                        ? `je ${plan.gels.carbs_each} g · ${fmtNumber(plan.gels.per_hour, 1)} pro Stunde${
                            plan.gels.caffeine
                              ? ` · ${plan.gels.caffeine} davon mit Koffein fürs letzte Drittel`
                              : ""
                          }`
                        : "Nur Trinken"}
                    </span>
                  </div>
                )}

                <div className="prep-row">
                  <span className="prep-key">Wasser</span>
                  <span className="prep-val">{fmtNumber(plan.total.water_ml)} ml</span>
                  <span className="prep-note">{plan.water.note}</span>
                </div>

                <div className="prep-row">
                  <span className="prep-key">Salz</span>
                  <span className="prep-val">
                    {plan.sodium.salt_g_total ? `${fmtNumber(plan.sodium.salt_g_total, 1)} g` : "—"}
                  </span>
                  <span className="prep-note">
                    {plan.syrup && plan.syrup.salt_g_per_shot
                      ? `${fmtNumber(plan.syrup.salt_g_per_shot, 2)} g pro Shot · direkt in den Sirup rühren`
                      : plan.sodium.salt_g_per_hour
                        ? `${fmtNumber(plan.sodium.salt_g_per_hour, 1)} g pro Stunde · Salztabletten oder Elektrolyte`
                        : plan.sodium.note}
                  </span>
                </div>
              </div>
            </Card>
          </section>

          {plan.surrounding.length > 0 && (
            <Card title="Drumherum" subtitle="Vortag, Frühstück und die erste Stunde danach">
              <div className="surround">
                {plan.surrounding.map((item) => (
                  <div className="surround-row" key={item.key}>
                    <span className="surround-label">{item.label}</span>
                    <span className="surround-value">{fmtNumber(item.carbs)} g</span>
                    <span className="surround-text">{item.text}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {plan.notes.length > 0 && (
            <section className="notes">
              {plan.notes.map((note, index) => (
                <p className="note" key={index}>
                  {note.text}
                </p>
              ))}
            </section>
          )}
        </>
      )}
    </div>
  );
}
