import { IconFuel, IconSync, IconToday } from "./icons";

export type Tab = "today" | "fuel";

const NAV: { key: Tab; label: string; icon: typeof IconToday }[] = [
  { key: "today", label: "Heute", icon: IconToday },
  { key: "fuel", label: "Verpflegung", icon: IconFuel },
];

export function Sidebar({
  tab,
  onTab,
  athlete,
  lastSync,
  onSync,
  syncing,
}: {
  tab: Tab;
  onTab: (tab: Tab) => void;
  athlete: string;
  lastSync: string | null;
  onSync: () => void;
  syncing: boolean;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark" />
        Cockpit
      </div>

      <nav className="nav">
        {NAV.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            className={tab === key ? "active" : ""}
            onClick={() => onTab(key)}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </nav>

      <div className="side-foot">
        <button type="button" className="side-sync" onClick={onSync} disabled={syncing}>
          <IconSync size={16} />
          {syncing ? "Synchronisiert…" : "Aktualisieren"}
        </button>
        <div className="who">
          {athlete}
          <span>
            {lastSync
              ? `Sync ${new Date(lastSync).toLocaleTimeString("de-AT", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}`
              : "Noch kein Sync"}
          </span>
        </div>
      </div>
    </aside>
  );
}
