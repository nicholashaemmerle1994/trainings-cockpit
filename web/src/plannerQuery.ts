import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { PlannerWeekResponse } from "./types";

export type PlannerSourceName = "plans" | "activities";

interface PlannerLoadState {
  data: PlannerWeekResponse | null;
  loading: boolean;
  stale: boolean;
  error: string | null;
  retrying: PlannerSourceName | null;
  reload: (source?: PlannerSourceName) => void;
  invalidate: (weeks: Array<string | null | undefined>) => void;
}

/**
 * Wochenabfrage mit Query-Schlüssel und veralteter Antwort.
 *
 * Der Cache ist absichtlich lokal: kein zweiter globaler Store. Ein Ergebnis
 * wird nur übernommen, wenn es zu genau der Woche gehört, die zuletzt gewählt
 * wurde. Eine langsame Vorwoche kann die neue Woche daher nicht überschreiben.
 */
export function usePlannerWeek(week: string, revision = 0): PlannerLoadState {
  const cache = useRef(new Map<string, PlannerWeekResponse>());
  const account = useRef<string | null>(null);
  const generation = useRef(0);
  const [data, setData] = useState<PlannerWeekResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<PlannerSourceName | null>(null);

  const load = useCallback(async (targetWeek: string, source?: PlannerSourceName) => {
    const run = ++generation.current;
    setLoading(true);
    setRetrying(source ?? null);
    setError(null);

    const cached = cache.current.get(targetWeek);
    if (cached && !source) {
      setData(cached);
      setStale(true);
    } else if (!cached) {
      setData(null);
      setStale(false);
    }

    try {
      const payload = await api.planner(targetWeek);
      // Zwei Schutzlinien: die laufende Anfrage muss die jüngste sein, und die
      // Antwort muss zu ihrem eigenen Query-Schlüssel gehören.
      if (run !== generation.current) return;
      if (payload.week !== targetWeek) return;
      // Ein Accountwechsel entwertet den lokalen Wochen-Cache vollständig;
      // eine Antwort eines anderen Accounts wird nie übernommen.
      if (account.current !== null && payload.account_id !== account.current) {
        cache.current.clear();
      }
      account.current = payload.account_id;
      cache.current.set(targetWeek, payload);
      setData(payload);
      setStale(false);
    } catch (cause) {
      if (run !== generation.current) return;
      setError(cause instanceof Error ? cause.message : "Woche konnte nicht geladen werden.");
      if (!cache.current.has(targetWeek)) setData(null);
    } finally {
      if (run === generation.current) {
        setLoading(false);
        setRetrying(null);
      }
    }
  }, []);

  useEffect(() => {
    void load(week);
    return () => {
      // Eine noch laufende Antwort dieser Woche wird beim Wechsel irrelevant.
      generation.current += 1;
    };
  }, [load, week, revision]);

  const reload = useCallback(
    (source?: PlannerSourceName) => {
      void load(week, source);
    },
    [load, week],
  );

  const invalidate = useCallback((weeks: Array<string | null | undefined>) => {
    for (const target of weeks) {
      if (target) cache.current.delete(target);
    }
  }, []);

  return { data, loading, stale, error, retrying, reload, invalidate };
}
