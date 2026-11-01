import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { Sidebar, type Tab } from "./components/Sidebar";
import { IconFuel, IconToday } from "./components/icons";
import { Fuel } from "./pages/Fuel";
import { Today } from "./pages/Today";
import type { Overview } from "./types";

const TABS: { key: Tab; label: string; icon: typeof IconToday }[] = [
  { key: "today", label: "Heute", icon: IconToday },
  { key: "fuel", label: "Verpflegung", icon: IconFuel },
];

/** Wie weit man ziehen muss, bevor der Sync losgeht. */
const PULL_THRESHOLD = 64;

function clockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" });
}

export default function App() {
  const [tab, setTab] = useState<Tab>("today");
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [popup, setPopup] = useState<string | null>(null);
  const [pull, setPull] = useState(0);
  const pullRef = useRef(0);

  const load = useCallback(async (): Promise<Overview | null> => {
    try {
      const overview = await api.overview();
      setData(overview);
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

  return (
    <div className="shell">
      <Sidebar
        tab={tab}
        onTab={setTab}
        athlete={data.athlete.name}
        lastSync={data.generated_at}
        onSync={() => void handleSync()}
        syncing={syncing}
      />

      <main className="main">
        {error && <div className="banner">{error}</div>}
        {tab === "today" && <Today data={data} />}
        {tab === "fuel" && <Fuel />}
      </main>

      <nav className="tabbar">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            className={tab === key ? "active" : ""}
            onClick={() => setTab(key)}
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
      <span className="brand-mark large" />
      <h1>Trainings-Cockpit</h1>
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
