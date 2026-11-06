import type { Tab } from "./tabs";

export interface RouteState {
  tab: Tab;
  week?: string;
  /** Event-ID einer Planung; getrennt von einer Aktivitätszeile. */
  plan?: number;
  /** Lokale Zeilen-ID der bestehenden kanonischen Aktivitätsansicht. */
  unit?: number;
  /** Die URL war eine gespeicherte Altliste und wurde bereits ersetzt. */
  legacy: boolean;
}

const PLANNER_PATHS = new Set([
  "/planer",
  "/planner",
  "/trainingsplaner",
  "/woche",
  "/week",
  "/planner/week",
  "/planer/week",
]);
const FUEL_PATHS = new Set(["/verpflegung", "/fuel"]);
const ACTIVITY_PATH = /^\/(?:aktivitaet|activity|einheit|unit)\/(\d+)$/;
const PLANNER_DATE_PATH = /^\/(?:planer|planner|woche|week)\/(\d{4}-\d{2}-\d{2})$/;

function normalisePath(path: string): string {
  if (path.length > 1 && path.endsWith("/")) return path.slice(0, -1);
  return path || "/";
}

function localDateInZone(date: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return `${value("year")}-${value("month")}-${value("day")}`;
}

/** Lokaler Kalendertag, nie ein UTC-Zeitpunkt. */
export function localDate(date = new Date(), timeZone?: string): string {
  if (timeZone) return localDateInZone(date, timeZone);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** Montag der Woche; der Sonntag gehört noch zur laufenden Woche. */
export function mondayOf(value: string): string {
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day, 12, 0, 0);
  const offset = (date.getDay() + 6) % 7;
  date.setDate(date.getDate() - offset);
  return localDate(date);
}

export function addDays(value: string, days: number): string {
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day + days, 12, 0, 0);
  return localDate(date);
}

export function currentPlannerWeek(now = new Date(), timeZone?: string): string {
  return mondayOf(localDate(now, timeZone));
}

export function validLocalDate(value: string | null | undefined): string | null {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day, 12, 0, 0);
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return null;
  }
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function firstParam(
  params: URLSearchParams,
  names: string[],
): string | null {
  for (const name of names) {
    const value = params.get(name);
    if (value) return value;
  }
  return null;
}

function positiveId(value: string | null | undefined): number | undefined {
  if (!value || !/^\d+$/.test(value)) return undefined;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function detailFromParams(params: URLSearchParams): { plan?: number; unit?: number } {
  return {
    plan: positiveId(params.get("plan") ?? params.get("planung")),
    unit: positiveId(
      params.get("einheit") ??
        params.get("unit") ??
        params.get("activity") ??
        params.get("aktivitaet"),
    ),
  };
}

function plannerWeekFromParams(params: URLSearchParams): string | undefined {
  // Ein gespeicherter Bereich wird nach Abschnitt 5.7 über sein Enddatum
  // verankert. Ein einzelnes Datum landet in dessen Woche.
  const ranged = firstParam(params, ["bis", "to", "end"]);
  const single = firstParam(params, [
    "woche",
    "week",
    "datum",
    "date",
    "tag",
    "von",
    "from",
    "start",
  ]);
  const validRange = validLocalDate(ranged);
  if (validRange) return mondayOf(validRange);
  const validSingle = validLocalDate(single);
  if (validSingle) return mondayOf(validSingle);
  return undefined;
}

/** Die aktuelle URL lesen; unbekannte Pfade fallen auf „Heute“ zurück. */
export function readRoute(location: Location = window.location): RouteState {
  const url = new URL(location.href);
  const path = normalisePath(url.pathname);
  const params = url.searchParams;
  const tabParam = (params.get("tab") ?? params.get("bereich") ?? "").toLowerCase();
  const plannerTab = ["woche", "week", "planer", "planner"].includes(tabParam);
  const fuelTab = ["fuel", "verpflegung"].includes(tabParam);
  const directActivity = ACTIVITY_PATH.exec(path);
  const datedPlanner = PLANNER_DATE_PATH.exec(path);
  const datedDate = datedPlanner ? validLocalDate(datedPlanner[1]) : null;
  const datedWeek = datedDate ? mondayOf(datedDate) : undefined;
  const detail = detailFromParams(params);
  // Ein direkter Aktivitätslink behält sein Detailziel. Der Pfad wird als
  // Altform in den Planer-Kontext überführt, damit Woche und Rücksprung
  // nachvollziehbar bleiben.
  if (directActivity || (detail.unit != null && !PLANNER_PATHS.has(path))) {
    return {
      tab: "planner",
      week: plannerWeekFromParams(params),
      unit: positiveId(directActivity?.[1]) ?? detail.unit,
      legacy: true,
    };
  }
  if (PLANNER_PATHS.has(path) || datedPlanner || plannerTab) {
    return {
      tab: "planner",
      week: plannerWeekFromParams(params) ?? datedWeek,
      ...detail,
      legacy:
        path === "/woche" ||
        path === "/week" ||
        path === "/planner/week" ||
        path === "/planer/week" ||
        datedPlanner != null ||
        plannerTab,
    };
  }
  if (FUEL_PATHS.has(path) || fuelTab) {
    return { tab: "fuel", legacy: false };
  }
  return { tab: "today", legacy: false };
}

/** Die kanonische URL eines bereits gelesenen Zustands. */
export function routeUrl(route: RouteState): string {
  if (route.tab === "planner") {
    return routePath("planner", route.week, {
      plan: route.plan,
      unit: route.unit,
    });
  }
  return routePath(route.tab);
}

export function routePath(
  tab: Tab,
  week?: string,
  detail?: { plan?: number; unit?: number },
): string {
  if (tab === "planner") {
    const params = new URLSearchParams();
    if (week) params.set("woche", week);
    if (detail?.plan != null) params.set("plan", String(detail.plan));
    if (detail?.unit != null) params.set("einheit", String(detail.unit));
    const query = params.toString();
    return query ? `/planer?${query}` : "/planer";
  }
  if (tab === "fuel") return "/verpflegung";
  return "/";
}

export function readStoredPlannerWeek(): string | undefined {
  try {
    const value = sessionStorage.getItem("tc.planner.week");
    return validLocalDate(value) ?? undefined;
  } catch {
    return undefined;
  }
}

export function storePlannerWeek(week: string): void {
  try {
    sessionStorage.setItem("tc.planner.week", week);
  } catch {
    /* Speicher kann im privaten Modus fehlen; die URL trägt die Woche. */
  }
}
