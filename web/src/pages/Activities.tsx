import { useEffect, useState } from "react";
import { api } from "../api";
import { ActivityTable } from "../components/ActivityTable";
import { EmptyState, Skeleton } from "../components/ui";
import { sportLabel } from "../format";
import type { ActivitiesResponse } from "../types";

export function Activities() {
  const [sport, setSport] = useState<string | undefined>(undefined);
  const [data, setData] = useState<ActivitiesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [visible, setVisible] = useState(40);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setVisible(40);
    api
      .activities(sport)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Fehler beim Laden");
      });
    return () => {
      cancelled = true;
    };
  }, [sport]);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>Aktivitäten</h1>
          <p className="meta">{data ? `${data.total} Einheiten` : "Verlauf"}</p>
        </div>
      </header>

      <div className="chips">
        <button
          type="button"
          className={`chip ${sport === undefined ? "active" : ""}`}
          onClick={() => setSport(undefined)}
        >
          Alle
        </button>
        {data?.sports.map((entry) => (
          <button
            key={entry.sport}
            type="button"
            className={`chip ${sport === entry.sport ? "active" : ""}`}
            onClick={() => setSport(entry.sport)}
          >
            {sportLabel(entry.sport)}
            <span className="chip-count">{entry.count}</span>
          </button>
        ))}
      </div>

      {error && <div className="banner">{error}</div>}

      {!data && !error && (
        <div className="card">
          <Skeleton height={40} />
          <Skeleton height={40} />
          <Skeleton height={40} />
        </div>
      )}

      {data && data.items.length === 0 && (
        <EmptyState title="Keine Einheiten" text="Für diesen Filter liegen keine Aktivitäten vor." />
      )}

      {data && data.items.length > 0 && (
        <>
          <section className="card">
            <ActivityTable items={data.items.slice(0, visible)} />
          </section>
          {data.items.length > visible && (
            <button
              type="button"
              className="chip load-more"
              onClick={() => setVisible((count) => count + 40)}
            >
              Mehr laden
              <span className="chip-count">{data.items.length - visible}</span>
            </button>
          )}
        </>
      )}
    </div>
  );
}
