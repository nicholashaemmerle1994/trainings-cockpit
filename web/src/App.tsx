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
  routeUrl,
  storePlannerWeek,
  type RouteState,
} from "./routing";
import {
  activeNavigationGuard,
  type NavigationGuard,
} from "./navigationGuard";
import { TABS, type Tab } from "./tabs";
import type { Overview } from "./types";
import { isPreview } from "./variant";

/** Wie weit man ziehen muss, bevor der Sync losgeht. */
const PULL_THRESHOLD = 64;

function clockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" });
}

function confirmedTime(iso: string): string {
  return new Date(iso).toLocaleString("de-AT", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function canonicalRoute(route: RouteState, timeZone?: string): string | null {
  if (route.tab === "planner") {
    const week =
      route.week ?? readStoredPlannerWeek() ?? currentPlannerWeek(new Date(), timeZone);
    const monday = mondayOf(week);
    if (route.legacy || route.week !== monday) {
      return routeUrl({ ...route, week: monday, legacy: false });
    }
    return null;
  }
  if (route.legacy) return routePath(route.tab);
  return null;
}

interface PendingNavigation {
  run?: () => void;
  history?: boolean;
}

export default function App() {
  const [route, setRoute] = useState<RouteState>(() => readRoute());
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [online, setOnline] = useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine,
  );
  const [revision, setRevision] = useState(0);
  const [popup, setPopup] = useState<string | null>(null);
  const [pull, setPull] = useState(0);
  const [navigationPrompt, setNavigationPrompt] = useState<{ saving: boolean } | null>(
    null,
  );
  const pullRef = useRef(0);
  const routeRef = useRef(route);
  const urlRef = useRef(`${window.location.pathname}${window.location.search}`);
  const pendingNavigation = useRef<PendingNavigation | null>(null);
  const allowNextPop = useRef(false);
  const scrollByWeek = useRef(new Map<string, number>());
  const previousRoute = useRef(route);

  useEffect(() => {
    routeRef.current = route;
    urlRef.current = `${window.location.pathname}${window.location.search}`;
  }, [route]);

  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  // Browser-Zurück läuft durch denselben Entwurfsschutz wie jede andere
  // Navigation. Der zurückgelegte Schritt wird zunächst unsichtbar rückgängig
  // gemacht; erst „Verwerfen“ geht ihn erneut und diesmal ohne Schutz.
  useEffect(() => {
    const onPop = () => {
      if (allowNextPop.current) {
        allowNextPop.current = false;
        setRoute(readRoute());
        return;
      }
      const next = readRoute();
      const nextUrl = `${window.location.pathname}${window.location.search}`;
      const guard = activeNavigationGuard();
      if (guard?.isDirty() && nextUrl !== urlRef.current) {
        window.history.pushState(null, "", urlRef.current);
        setRoute(routeRef.current);
        pendingNavigation.current = { history: true };
        setNavigationPrompt({ saving: guard.isSaving() });
        return;
      }
      setRoute(next);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      const guard = activeNavigationGuard();
      if (!guard?.isDirty()) return;
      event.preventDefault();
      // Safari und ältere Browser brauchen einen gesetzten Rückgabewert.
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);

  // Scrollposition gehört zur gewählten Woche, nicht zur Detailansicht.
  useEffect(() => {
    const previous = previousRoute.current;
    const leavingDetails =
      previous.tab === "planner" &&
      (previous.plan != null || previous.unit != null) &&
      route.tab === "planner" &&
      route.plan == null &&
      route.unit == null;
    const enteringPlanner =
      previous.tab !== "planner" && route.tab === "planner";
    if ((leavingDetails || enteringPlanner) && route.week) {
      const key = `planner:${mondayOf(route.week)}`;
      const target = scrollByWeek.current.get(key);
      if (target != null) {
        window.requestAnimationFrame(() => window.scrollTo(0, target));
      }
    }
    previousRoute.current = route;
  }, [route]);

  const rememberScroll = useCallback(() => {
    if (routeRef.current.tab !== "planner" || !routeRef.current.week) return;
    scrollByWeek.current.set(
      `planner:${mondayOf(routeRef.current.week)}`,
      window.scrollY,
    );
  }, []);

  const requestNavigation = useCallback((run: () => void) => {
    const guard: NavigationGuard | null = activeNavigationGuard();
    if (guard?.isDirty()) {
      pendingNavigation.current = { run };
      setNavigationPrompt({ saving: guard.isSaving() });
      return false;
    }
    run();
    return true;
  }, []);

  const confirmDiscard = useCallback(() => {
    const pending = pendingNavigation.current;
    const guard = activeNavigationGuard();
    guard?.discard();
    pendingNavigation.current = null;
    setNavigationPrompt(null);
    if (pending?.history) {
      allowNextPop.current = true;
      window.setTimeout(() => window.history.back(), 0);
      return;
    }
    pending?.run?.();
  }, []);

  const keepEditing = useCallback(() => {
    pendingNavigation.current = null;
    setNavigationPrompt(null);
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
      requestNavigation(() => {
        rememberScroll();
        const week =
          tab === "planner"
            ? (route.week ??
              readStoredPlannerWeek() ??
              currentPlannerWeek(new Date(), data?.time_zone))
            : undefined;
        if (week) storePlannerWeek(week);
        window.history.pushState(null, "", routePath(tab, week));
        setRoute(readRoute());
      });
    },
    [route.tab, route.week, data?.time_zone, requestNavigation, rememberScroll],
  );

  const changeWeek = useCallback((week: string) => {
    storePlannerWeek(week);
    // Wochenwechsel ersetzen denselben Eintrag; sie stapeln keine Zurück-Schritte.
    window.history.replaceState(null, "", routePath("planner", week));
    setRoute(readRoute());
    window.scrollTo(0, 0);
  }, []);

  const plannerWeek = useCallback((): string => {
    const week =
      route.week ??
      readStoredPlannerWeek() ??
      currentPlannerWeek(new Date(), data?.time_zone);
    return mondayOf(week);
  }, [route.week, data?.time_zone]);

  const openPlan = useCallback(
    (planId: number) => {
      requestNavigation(() => {
        rememberScroll();
        window.history.pushState(
          null,
          "",
          routePath("planner", plannerWeek(), { plan: planId, unit: route.unit }),
        );
        setRoute(readRoute());
      });
    },
    [plannerWeek, route.unit, requestNavigation, rememberScroll],
  );

  const openUnit = useCallback(
    (rowId: number) => {
      requestNavigation(() => {
        rememberScroll();
        window.history.pushState(
          null,
          "",
          routePath("planner", plannerWeek(), { unit: rowId }),
        );
        setRoute(readRoute());
      });
    },
    [plannerWeek, requestNavigation, rememberScroll],
  );

  const closePlan = useCallback(() => {
    requestNavigation(() => {
      window.history.replaceState(
        null,
        "",
        routePath("planner", plannerWeek(), { unit: route.unit }),
      );
      setRoute(readRoute());
    });
  }, [plannerWeek, route.unit, requestNavigation]);

  const closeUnit = useCallback(() => {
    requestNavigation(() => {
      window.history.replaceState(null, "", routePath("planner", plannerWeek()));
      setRoute(readRoute());
    });
  }, [plannerWeek, requestNavigation]);

  /** Nach bestätigtem Speichern die ganze Detailkette verlassen. */
  const closeDetails = useCallback(
    (week?: string) => {
      const target = mondayOf(week ?? plannerWeek());
      storePlannerWeek(target);
      window.history.replaceState(null, "", routePath("planner", target));
      setRoute(readRoute());
    },
    [plannerWeek],
  );

  const load = useCallback(async (): Promise<Overview | null> => {
    try {
      const overview = await api.overview();
      setData(withDemoRecovery(overview));
      setError(null);
      return overview;
    } catch (err) {
      setOnline(typeof navigator === "undefined" ? true : navigator.onLine);
      setError(
        typeof navigator !== "undefined" && !navigator.onLine
          ? "Offline – der zuletzt bestätigte Stand bleibt sichtbar."
          : err instanceof Error
            ? err.message
            : "Daten konnten nicht geladen werden.",
      );
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
    if (typeof navigator !== "undefined" && !navigator.onLine) {
      setOnline(false);
      setError("Offline – es wurde nichts synchronisiert.");
      setSyncing(false);
      return;
    }
    try {
      await api.sync();
      const fresh = await load();
      // Der Sync aktualisiert Wochenliste, Aktivitätsdetails und die
      // rollierende Dashboard-Karte. Veraltete Antworten werden über die
      // Revisionsnummer und die Query-Generation verworfen.
      setRevision((current) => current + 1);
      // Die Zeit kommt aus dem Datensatz, nicht aus der Uhr des Geräts — sonst
      // steht im Kopf eine andere Minute als im Hinweis.
      if (fresh) setPopup(`Aktualisiert ${clockTime(fresh.generated_at)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync fehlgeschlagen.");
    } finally {
      setSyncing(false);
    }
  }, [load]);

  const handlePlannerChanged = useCallback(() => {
    void load();
    setRevision((current) => current + 1);
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
  const selectedWeek =
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
        {!online && (
          <div className="banner banner--offline" role="status">
            <strong>Offline</strong> · bestätigter Stand vom{" "}
            {confirmedTime(data.generated_at)}. Es wird nichts remote gespeichert.
          </div>
        )}
        {error && <div className="banner">{error}</div>}
        {route.tab === "today" && (
          <Today
            data={data}
            accountId={data.account_id ?? "default"}
            athleteId={data.athlete_id ?? "default"}
            online={online}
            revision={revision}
            onDataChanged={handlePlannerChanged}
          />
        )}
        {route.tab === "planner" && (
          <Planner
            key={data.account_id ?? data.athlete.name}
            week={selectedWeek}
            timeZone={data.time_zone}
            accountId={data.account_id ?? "default"}
            athleteId={data.athlete_id ?? "default"}
            online={online}
            onWeekChange={changeWeek}
            openPlan={route.plan ?? null}
            openUnit={route.unit ?? null}
            onOpenPlan={openPlan}
            onOpenUnit={openUnit}
            onClosePlan={closePlan}
            onCloseUnit={closeUnit}
            onCloseDetails={closeDetails}
            onGuardNavigation={requestNavigation}
            revision={revision}
            onDataChanged={handlePlannerChanged}
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

      {navigationPrompt && (
        <NavigationDialog
          saving={navigationPrompt.saving}
          onKeep={keepEditing}
          onDiscard={confirmDiscard}
        />
      )}
    </div>
  );
}

function NavigationDialog({
  saving,
  onKeep,
  onDiscard,
}: {
  saving: boolean;
  onKeep: () => void;
  onDiscard: () => void;
}) {
  const keepRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    // „Weiterbearbeiten“ ist die sichere Voreinstellung.
    keepRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onKeep();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onKeep]);
  return (
    <div className="guard-backdrop" role="presentation">
      <div
        className="guard-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="guard-title"
        aria-describedby="guard-text"
      >
        <h2 id="guard-title">Ungespeicherte Änderungen</h2>
        <p id="guard-text">
          {saving
            ? "Ein Speichervorgang ist noch offen. Verlassen macht ihn nicht rückgängig; der Vorgang bleibt in der Liste der offenen Vorgänge erhalten."
            : "Der lokale Entwurf bleibt als Wiederherstellung gesichert. Verwerfen entfernt ihn ohne Remote-Änderung."}
        </p>
        <div className="guard-dialog__actions">
          <button
            ref={keepRef}
            type="button"
            className="btn btn--ghost"
            onClick={onKeep}
          >
            Weiterbearbeiten
          </button>
          <button
            type="button"
            className="btn btn--ghost guard-dialog__discard"
            onClick={onDiscard}
          >
            Verwerfen und verlassen
          </button>
        </div>
      </div>
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
