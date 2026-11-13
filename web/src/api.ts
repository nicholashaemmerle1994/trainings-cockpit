import type {
  CopyJobResponse,
  CopyJobsResponse,
  CopyPreview,
  FuelPlan,
  Overview,
  PlanDetail,
  PlanDraftProjection,
  PlannerDeleteResponse,
  PlannerOperationsResponse,
  PlannerSaveResponse,
  PlannerWeekResponse,
  SyncResult,
  TemplateDetail,
  TemplateListResponse,
  TemplateProjection,
  UnitDetail,
  UnitPlanLinkContext,
} from "./types";

/** Ein API-Fehler mit dem stabilen Code der Planner-Grenze. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;
  readonly cloneCode: string | null;

  constructor(
    message: string,
    options: { status: number; code?: string | null; cloneCode?: string | null },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.code = options.code ?? null;
    this.cloneCode = options.cloneCode ?? null;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { Accept: "application/json" },
    ...init,
  });
  if (!response.ok) {
    let message = response.statusText;
    let code: string | null = null;
    let cloneCode: string | null = null;
    try {
      const body = (await response.json()) as {
        detail?: string | { code?: string; message?: string; clone_code?: string };
      };
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (body.detail && typeof body.detail === "object") {
        message = body.detail.message ?? message;
        code = body.detail.code ?? null;
        cloneCode = body.detail.clone_code ?? null;
      }
    } catch {
      /* Kein JSON: der Statustext bleibt die Erklärung. */
    }
    throw new ApiError(message, { status: response.status, code, cloneCode });
  }
  return (await response.json()) as T;
}

export const api = {
  overview: () => request<Overview>("/api/overview?days=90"),
  planner: (week?: string) =>
    request<PlannerWeekResponse>(
      `/api/planner${week ? `?week=${encodeURIComponent(week)}` : ""}`,
    ),
  planDetail: (eventId: number) =>
    request<PlanDetail>(`/api/planner/plan/${eventId}`),
  planRemote: (eventId: number) =>
    request<PlanDetail>(`/api/planner/plan/${eventId}/remote`),
  planDraft: (eventId: number, body: unknown) =>
    request<PlanDraftProjection>(`/api/planner/plan/${eventId}/draft`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  savePlan: (eventId: number, body: unknown) =>
    request<PlannerSaveResponse>(`/api/planner/plan/${eventId}/save`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  movePlan: (eventId: number, date: string) =>
    request<PlannerSaveResponse>(`/api/planner/plan/${eventId}/move`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ date }),
    }),
  saveNewPlan: (body: unknown) =>
    request<PlannerSaveResponse>("/api/planner/draft/save", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deletePlan: (eventId: number) =>
    request<PlannerDeleteResponse>(`/api/planner/plan/${eventId}`, {
      method: "DELETE",
    }),
  openOperations: () =>
    request<PlannerOperationsResponse>("/api/planner/operations"),
  reconcileOperation: (operationId: string) =>
    request<{
      status: PlannerSaveResponse["status"];
      confirmed: unknown | null;
      week: string | null;
      time_zone: string;
    }>(`/api/planner/operations/${encodeURIComponent(operationId)}/reconcile`, {
      method: "POST",
    }),
  newPlanDraft: (body: unknown) =>
    request<PlanDraftProjection>("/api/planner/draft/new", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  templates: () =>
    request<TemplateListResponse>("/api/planner/templates"),
  templateDetail: (templateId: string) =>
    request<TemplateDetail>(
      `/api/planner/templates/${encodeURIComponent(templateId)}`,
    ),
  saveTemplateFromPlan: (eventId: number, name: string) =>
    request<TemplateDetail>(
      `/api/planner/templates/from-plan/${eventId}`,
      {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      },
    ),
  projectTemplate: (templateId: string, date: string, draftId: string) =>
    request<TemplateProjection>(
      `/api/planner/templates/${encodeURIComponent(templateId)}/project`,
      {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ date, draft_id: draftId }),
      },
    ),
  deleteTemplate: (templateId: string) =>
    request<{ deleted: true; template_id: string }>(
      `/api/planner/templates/${encodeURIComponent(templateId)}`,
      { method: "DELETE" },
    ),
  copyPreview: (body: {
    source_start: string;
    weeks: number;
    target_start?: string;
  }) =>
    request<CopyPreview>("/api/planner/copy/preview", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  startCopyJob: (body: {
    source_start: string;
    weeks: number;
    target_start?: string;
    client_request_id: string;
  }) =>
    request<CopyJobResponse>("/api/planner/copy/jobs", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  openCopyJobs: () =>
    request<CopyJobsResponse>("/api/planner/copy/jobs?state=open"),
  copyJob: (jobId: string) =>
    request<CopyJobResponse>(
      `/api/planner/copy/jobs/${encodeURIComponent(jobId)}`,
    ),
  advanceCopyJob: (jobId: string) =>
    request<CopyJobResponse>(
      `/api/planner/copy/jobs/${encodeURIComponent(jobId)}/advance`,
      { method: "POST" },
    ),
  unit: (rowId: number) => request<UnitDetail>(`/api/unit/${rowId}`),
  unitPlanLink: (rowId: number) =>
    request<UnitPlanLinkContext>(`/api/unit/${rowId}/plan-link`),
  linkUnitPlan: (rowId: number, planId: number) =>
    request<UnitPlanLinkContext>(`/api/unit/${rowId}/plan-link`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ plan_id: planId }),
    }),
  unlinkUnitPlan: (rowId: number, planId: number) =>
    request<UnitPlanLinkContext>(
      `/api/unit/${rowId}/plan-link?plan_id=${encodeURIComponent(String(planId))}`,
      { method: "DELETE" },
    ),
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
