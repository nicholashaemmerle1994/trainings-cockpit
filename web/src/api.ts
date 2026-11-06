import type {
  ActivitiesResponse,
  FuelPlan,
  Overview,
  PlanDetail,
  PlanDraftProjection,
  PlannerWeekResponse,
  SessionDetail,
  SyncResult,
  UnitDetail,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const api = {
  overview: () => request<Overview>("/api/overview?days=90"),
  activities: (sport?: string) =>
    request<ActivitiesResponse>(
      `/api/activities?limit=300${sport ? `&sport=${encodeURIComponent(sport)}` : ""}`,
    ),
  session: (id: number) => request<SessionDetail>(`/api/session/${id}`),
  planner: (week?: string) =>
    request<PlannerWeekResponse>(
      `/api/planner${week ? `?week=${encodeURIComponent(week)}` : ""}`,
    ),
  planDetail: (eventId: number) =>
    request<PlanDetail>(`/api/planner/plan/${eventId}`),
  planDraft: (eventId: number, body: unknown) =>
    request<PlanDraftProjection>(`/api/planner/plan/${eventId}/draft`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  newPlanDraft: (body: unknown) =>
    request<PlanDraftProjection>("/api/planner/draft/new", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  unit: (rowId: number) => request<UnitDetail>(`/api/unit/${rowId}`),
  fuel: (params: {
    minutes: number;
    mode: string;
    weight?: number | null;
    temp: number;
    source: string;
    shot: number;
    unit: string;
  }) => {
    const query = new URLSearchParams({
      minutes: String(params.minutes),
      mode: params.mode,
      temp: String(params.temp),
      source: params.source,
      shot: String(params.shot),
      unit: params.unit,
    });
    if (params.weight) query.set("weight", String(params.weight));
    return request<FuelPlan>(`/api/fuel?${query.toString()}`);
  },
  vendorScore: (day: string, score: number) =>
    request<{ date: string; score: number; saved: number | null }>(
      `/api/vendor-score?day=${day}&score=${score}`,
      { method: "POST" },
    ),
  sync: () => request<SyncResult>("/api/sync", { method: "POST" }),
};
