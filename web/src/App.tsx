import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { BrandMark, DemoTag, PreviewTag } from "./components/Brand";
import { Sidebar } from "./components/Sidebar";
import { Fuel } from "./pages/Fuel";
import { Planner } from "./pages/Planner";
import { Today } from "./pages/Today";
import { withDemoRecovery } from "./demo";
import {
  currentPlannerWeek,
  mondayOf,
  readRoute,
  readStoredPlannerWeek,
  routePath,
  storePlannerWeek,
  type RouteState,
} from "./routing";
import { TABS, type Tab } from "./tabs";
import type { Overview } from "./types";
import { isPreview } from "./variant";

/** Wie weit man ziehen muss, bevor der Sync losgeht. */
const PULL_THRESHOLD = 64;

function clockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" });
}

function canonicalRoute(route: RouteState, timeZone?: string): string | null {
  if (route.tab === "planner") {
    const week =
      route.week ?? readStoredPlannerWeek() ?? currentPlannerWeek(new Date(), timeZone);
    const monday = mondayOf(week);
    if (route.legacy || route.week !== monday) return routePath("planner", monday);
    return null;
  }
  if (route.legacy) return routePath(route.tab);
  return null;
}

export default function App() {
  const [route, setRoute] = useState<RouteState>(() => readRoute());
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [popup, setPopup] = useState<string | null>(null);
  const [pull, setPull] = useState(0);
  const pullRef = useRef(0);

  useEffect(() => {
    const onPop = () => setRoute(readRoute());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  // Altlisten-URLs werden ersetzt, nicht gestapelt: Zurück erzeugt keine
  // Schleife und öffnet keine zweite Liste. Auch ein Tagesdatum in der Woche
  // wird auf den Montag normalisiert.
  useEffect(() => {
    const target = canonicalRoute(route, data?.time_zone);
    if (!target) return;
    const current = `${window.location.pathname}${window.location.search}`;
    if (current === target) return;
    window.history.replaceState(null, "", target);
    setRoute(readRoute());
  }, [route, data?.time_zone]);

  useEffect(() => {
    if (route.tab === "planner" && route.week) storePlannerWeek(route.week);
  }, [route.tab, route.week]);

  const goTab = useCallback(
    (tab: Tab) => {
      if (tab === route.tab && tab !== "planner") return;
      const week =
        tab === "planner"
          ? (route.week ??
            readStoredPlannerWeek() ??
            currentPlannerWeek(new Date(), data?.time_zone))
          : undefined;
      if (week) storePlannerWeek(week);
      window.history.pushState(null, "", routePath(tab, week));
      setRoute(readRoute());
    },
    [route.tab, route.week, data?.time_zone],
  );

  const changeWeek = useCallback((week: string) => {
    storePlannerWeek(week);
    // Wochenwechsel ersetzen denselben Eintrag; sie stapeln keine Zurück-Schritte.
    window.history.replaceState(null, "", routePath("planner", week));
    setRoute(readRoute());
  }, []);

  const load = useCallback(async (): Promise<Overview | null> => {
    try {
      const overview = await api.overview();
      setData(withDemoRecovery(overview));
      setError(null);
      return overview;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Daten konnten nicht geladen werden.");
      return null;
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!popup) return;
    const timer = setTimeout(() => setPopup(null), 2800);
    return () => clearTimeout(timer);
  }, [popup]);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    setError(null);
    try {
      await api.sync();
      const fresh = await load();
      // Die Zeit kommt aus dem Datensatz, nicht aus der Uhr des Geräts — sonst
      // steht im Kopf eine andere Minute als im Hinweis.
      if (fresh) setPopup(`Aktualisiert ${clockTime(fresh.generated_at)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync fehlgeschlagen.");
    } finally {
      setSyncing(false);
    }
  }, [load]);

  // Ziehen zum Nachladen: nur am oberen Rand, nur mit einem Finger.
  useEffect(() => {
    let startY: number | null = null;

    const start = (event: TouchEvent) => {
      if (event.touches.length !== 1 || window.scrollY > 0 || syncing) return;
      startY = event.touches[0].clientY;
    };

    const move = (event: TouchEvent) => {
      if (startY == null) return;
      const delta = event.touches[0].clientY - startY;
      if (delta <= 0 || window.scrollY > 0) {
        startY = null;
        pullRef.current = 0;
        setPull(0);
        return;
      }
      const damped = Math.min(96, delta * 0.5);
      pullRef.current = damped;
      setPull(damped);
      if (event.cancelable && delta > 8) event.preventDefault();
    };

    const end = () => {
      if (startY == null) return;
      startY = null;
      const value = pullRef.current;
      pullRef.current = 0;
      setPull(0);
      if (value >= PULL_THRESHOLD) void handleSync();
    };

    window.addEventListener("touchstart", start, { passive: true });
    window.addEventListener("touchmove", move, { passive: false });
    window.addEventListener("touchend", end);
    window.addEventListener("touchcancel", end);
    return () => {
      window.removeEventListener("touchstart", start);
      window.removeEventListener("touchmove", move);
      window.removeEventListener("touchend", end);
      window.removeEventListener("touchcancel", end);
    };
  }, [handleSync, syncing]);

  if (!data) {
    return <Splash error={error} onRetry={() => void load()} />;
  }

  const pulling = pull > 0 && !syncing;
  const plannerWeek =
    route.week ??
    readStoredPlannerWeek() ??
    currentPlannerWeek(new Date(), data.time_zone);

  return (
    <div className="shell">
      <Sidebar
        tab={route.tab}
        onTab={goTab}
        athlete={data.athlete.name}
        lastSync={data.generated_at}
        onSync={() => void handleSync()}
        syncing={syncing}
      />

      <main className="main">
        {isPreview && (
          <div className="preview-brand" aria-label="Vorschau-Version">
            <BrandMark />
            <span className="preview-name">Cockpit</span>
            <PreviewTag />
            <DemoTag />
          </div>
        )}
        {error && <div className="banner">{error}</div>}
        {route.tab === "today" && <Today data={data} />}
        {route.tab === "planner" && (
          <Planner
            week={plannerWeek}
            timeZone={data.time_zone}
            onWeekChange={changeWeek}
          />
        )}
        {route.tab === "fuel" && <Fuel />}
      </main>

      <nav className="tabbar">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            className={route.tab === key ? "active" : ""}
            aria-current={route.tab === key ? "page" : undefined}
            onClick={() => goTab(key)}
          >
            <Icon size={18} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div
        className={`pull ${pull > 0 || syncing ? "on" : ""}`}
        style={{ transform: `translate(-50%, ${syncing ? 0 : Math.min(pull, PULL_THRESHOLD) * 0.5}px)` }}
        aria-hidden={!(pull > 0 || syncing)}
      >
        {syncing
          ? "Wird aktualisiert…"
          : pulling && pull >= PULL_THRESHOLD
            ? "Loslassen zum Aktualisieren"
            : "Ziehen zum Aktualisieren"}
      </div>

      {popup && (
        <div className="popup" role="status">
          {popup}
        </div>
      )}
    </div>
  );
}

function Splash({ error, onRetry }: { error: string | null; onRetry: () => void }) {
  return (
    <div className="splash">
      <BrandMark large />
      <h1>Trainings-Cockpit</h1>
      <PreviewTag />
      {error ? (
        <>
          <p className="error">{error}</p>
          <button type="button" className="sync-btn" onClick={onRetry}>
            Erneut versuchen
          </button>
        </>
      ) : (
        <p className="muted">Daten werden geladen…</p>
      )}
    </div>
  );
}
