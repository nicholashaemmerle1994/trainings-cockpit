import { useState } from "react";
import { api } from "../api";
import { fmtSigned } from "../format";

/**
 * Der Score der Vergleichs-App (Bevel) für heute.
 *
 * Er zählt nicht in die Erholung hinein — er ist der Maßstab, an dem das eigene
 * Modell gemessen wird (D-22, D-52). Deshalb steht er als stille Zeile in der
 * Karte und verschwindet, sobald das Vergleichsfenster vorbei ist.
 */
export function VendorScore({
  day,
  initial,
  score,
}: {
  day: string;
  initial: number | null;
  score: number | null;
}) {
  const [text, setText] = useState(initial == null ? "" : String(Math.round(initial)));
  const [gespeichert, setGespeichert] = useState<number | null>(initial);
  const [fehler, setFehler] = useState(false);
  const [frisch, setFrisch] = useState(false);

  const zahl = text.trim() === "" ? null : Number(text);
  const gueltig = zahl != null && Number.isFinite(zahl) && zahl >= 0 && zahl <= 100;

  async function speichern() {
    if (!gueltig || zahl === gespeichert) return;
    setFehler(false);
    try {
      await api.vendorScore(day, zahl);
      setGespeichert(zahl);
      setFrisch(true);
    } catch {
      setFehler(true);
    }
  }

  const differenz =
    score != null && gespeichert != null ? Math.round(score - gespeichert) : null;

  return (
    <div className="vendor">
      <label className="vendor-row" htmlFor="vendor-score">
        <span className="vendor-label">Bevel</span>
        <input
          id="vendor-score"
          type="number"
          min={0}
          max={100}
          inputMode="numeric"
          enterKeyHint="done"
          placeholder="—"
          value={text}
          aria-label="Bevel-Wert für heute"
          onChange={(event) => setText(event.target.value)}
          onBlur={speichern}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              event.currentTarget.blur();
            }
          }}
        />
      </label>
      {differenz != null ? (
        <p className="vendor-note">
          Cockpit {Math.round(score ?? 0)} · Bevel {gespeichert} · {fmtSigned(differenz)} Punkte
        </p>
      ) : (
        frisch && <p className="vendor-note">gespeichert</p>
      )}
      {text.trim() !== "" && !gueltig && (
        <p className="vendor-note">Wert zwischen 0 und 100</p>
      )}
      {fehler && <p className="vendor-note vendor-note-bad">nicht gespeichert</p>}
    </div>
  );
}
