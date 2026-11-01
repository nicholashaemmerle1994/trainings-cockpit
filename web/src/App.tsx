import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Sidebar, type Tab } from "./components/Sidebar";
import { IconFuel, IconList, IconToday } from "./components/icons";
import { Activities } from "./pages/Activities";
import { Fuel } from "./pages/Fuel";
import { Today } from "./pages/Today";
import type { Overview } from "./types";

const TABS: { key: Tab; label: string; icon: typeof IconToday }[] = [
  { key: "today", label: "Heute", icon: IconToday },
  { key: "fuel", label: "Verpflegung", icon: IconFuel },
  { key: "activities", label: "Aktivitäten", icon: IconList },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("today");
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncedAt, setSyncedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const overview = await api.overview();
      setData(overview);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Daten konnten nicht geladen werden.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    setError(null);
    try {
      await api.sync();
      await load();
      setSyncedAt(new Date().toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync fehlgeschlagen.");
    } finally {
      setSyncing(false);
    }
  }, [load]);

  if (!data) {
    return <Splash error={error} onRetry={() => void load()} />;
  }

  return (
    <div className="shell">
      <Sidebar
        tab={tab}
        onTab={setTab}
        athlete={data.athlete.name}
        lastSync={data.generated_at}
      />

      <main className="main">
        {error && <div className="banner">{error}</div>}
        {tab === "today" && (
          <Today
            data={data}
            onOpenActivities={() => setTab("activities")}
            onRefresh={() => void load()}
            onSync={() => void handleSync()}
            syncing={syncing}
          />
        )}
        {tab === "fuel" && <Fuel />}
        {tab === "activities" && <Activities />}
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

      {syncedAt && <span className="sync-toast">Aktualisiert {syncedAt}</span>}
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
