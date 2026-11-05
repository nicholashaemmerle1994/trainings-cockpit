import { TABS, type Tab } from "../tabs";
import { BrandMark, PreviewTag } from "./Brand";
import { IconSync } from "./icons";

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
        <BrandMark />
        Cockpit
        <PreviewTag />
      </div>

      <nav className="nav">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            className={tab === key ? "active" : ""}
            aria-current={tab === key ? "page" : undefined}
            onClick={() => onTab(key)}
          >
            <Icon size={18} />
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
