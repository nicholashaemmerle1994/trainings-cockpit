import { IconCalendar, IconFuel, IconToday } from "./components/icons";

export type Tab = "today" | "planner" | "fuel";

/** Die eine Liste der Hauptbereiche; Seitenleiste und Tableiste lesen sie. */
export const TABS: { key: Tab; label: string; icon: typeof IconToday }[] = [
  { key: "today", label: "Heute", icon: IconToday },
  { key: "planner", label: "Planer", icon: IconCalendar },
  { key: "fuel", label: "Verpflegung", icon: IconFuel },
];
