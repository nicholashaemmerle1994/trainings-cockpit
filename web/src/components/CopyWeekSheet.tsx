import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { fmtDateLong, fmtKm, fmtSpan } from "../format";
import { addDays, mondayOf } from "../routing";
import type { CopyItem, CopyJob, CopyPreview, CopyPreviewItem } from "../types";
import { Sheet } from "./Sheet";
import { StatusBadge } from "./ui";

const WEEK_COUNTS = [1, 2, 3, 4] as const;

const JOB_STATE_LABEL: Record<CopyJob["state"], string> = {
  queued: "Vorbereitet",
  running: "Läuft",
  completed: "Abgeschlossen",
  partial: "Teilweise abgeschlossen",
  failed: "Nicht abgeschlossen",
};

const ITEM_STATE_LABEL: Record<CopyItem["state"], string> = {
  pending: "Wartet",
  created: "Angelegt",
  saved_unverified: "Angelegt, ungeprüft",
  unknown: "Unklar",
  failed: "Fehlgeschlagen",
  conflict: "Konflikt",
  skipped: "Bereits vorhanden",
};

function previewItemMeta(item: CopyPreviewItem): string {
  const parts = [item.sport_label, fmtDateLong(item.source_date)];
  if (item.seconds != null && item.seconds > 0) parts.push(fmtSpan(item.seconds));
  if (item.metres != null && item.metres > 0) parts.push(fmtKm(item.metres / 1000));
  return parts.join(" · ");
}

function copyError(cause: unknown): string {
  if (cause instanceof ApiError) {
    if (cause.code === "copy_running") {
      return "Für diesen Zeitraum läuft bereits eine Kopie. Öffne sie unten und setze sie fort.";
    }
    return cause.message;
  }
  return cause instanceof Error
    ? cause.message
    : "Die Kopie konnte nicht vorbereitet werden.";
}

function newRequestId(): string {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `copy:${random}`;
}

/**
 * Wochen- und Blockkopie.
 *
 * Die Vorschau ist rein lesend. Erst „Kopieren“ legt einen persistenten Job an;
 * danach wird immer genau ein Item über den vorhandenen Speicherweg
 * verarbeitet. Ein Neustart kann den Job über „Fortsetzen“ wieder aufnehmen.
 */
export function CopyWeekSheet({
  week,
  online,
  onClose,
  onFinished,
  onOpenWeek,
}: {
  week: string;
  online: boolean;
  onClose: () => void;
  onFinished: (job: CopyJob) => void;
  onOpenWeek: (week: string) => void;
}) {
  const sourceStart = mondayOf(week);
  const [weeks, setWeeks] = useState(1);
  const [multiOpen, setMultiOpen] = useState(false);
  const [target, setTarget] = useState(() => addDays(sourceStart, 7));
  const targetTouched = useRef(false);
  const [preview, setPreview] = useState<CopyPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewNonce, setPreviewNonce] = useState(0);
  const [job, setJob] = useState<CopyJob | null>(null);
  const [items, setItems] = useState<CopyItem[]>([]);
  const [starting, setStarting] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [jobError, setJobError] = useState<string | null>(null);
  const [openJobs, setOpenJobs] = useState<CopyJob[]>([]);
  const [openJobsError, setOpenJobsError] = useState<string | null>(null);
  const [resuming, setResuming] = useState<string | null>(null);
  const requestId = useRef<string | null>(null);
  const startLock = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const loadOpenJobs = () => {
    api
      .openCopyJobs()
      .then((result) => {
        if (mounted.current) {
          setOpenJobs(result.jobs);
          setOpenJobsError(null);
        }
      })
      .catch((cause: unknown) => {
        if (mounted.current) {
          setOpenJobsError(
            cause instanceof Error
              ? cause.message
              : "Offene Kopien konnten nicht geladen werden.",
          );
        }
      });
  };

  useEffect(() => {
    loadOpenJobs();
  }, []);

  useEffect(() => {
    if (job != null) return;
    let alive = true;
    setPreviewLoading(true);
    setPreviewError(null);
    const timer = window.setTimeout(() => {
      api
        .copyPreview({
          source_start: sourceStart,
          weeks,
          target_start: target,
        })
        .then((result) => {
          if (!alive) return;
          setPreview(result);
          setPreviewLoading(false);
        })
        .catch((cause: unknown) => {
          if (!alive) return;
          setPreview(null);
          setPreviewLoading(false);
          setPreviewError(copyError(cause));
        });
    }, 220);
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [job, sourceStart, weeks, target, previewNonce]);

  const changeWeeks = (next: number) => {
    setWeeks(next);
    if (!targetTouched.current) {
      setTarget(addDays(sourceStart, 7 * next));
    }
    requestId.current = null;
  };

  const changeTarget = (value: string) => {
    if (!value) return;
    targetTouched.current = true;
    setTarget(mondayOf(value));
    requestId.current = null;
  };

  const surfaceJob = (nextJob: CopyJob, nextItems: CopyItem[]) => {
    setJob(nextJob);
    setItems(nextItems);
    if (nextItems.length > 0) setPreview(null);
    if (["completed", "partial", "failed"].includes(nextJob.state)) {
      onFinished(nextJob);
    }
  };

  const advanceUntilPaused = async (jobId: string) => {
    setAdvancing(true);
    setJobError(null);
    try {
      let current = await api.copyJob(jobId);
      if (!mounted.current) return;
      surfaceJob(current.job, current.items);
      let guard = 0;
      while (current.job.pending > 0 && current.job.can_advance && guard < 64) {
        guard += 1;
        current = await api.advanceCopyJob(jobId);
        if (!mounted.current) return;
        surfaceJob(current.job, current.items);
        if (!current.job.can_advance) break;
      }
      if (guard >= 64) {
        setJobError(
          "Der Vorgang ist noch nicht abgeschlossen. Setze ihn über „Fortsetzen“ weiter fort.",
        );
      }
      loadOpenJobs();
    } catch (cause: unknown) {
      if (!mounted.current) return;
      setJobError(copyError(cause));
      loadOpenJobs();
    } finally {
      if (mounted.current) setAdvancing(false);
    }
  };

  const start = async () => {
    if (startLock.current || !preview || preview.blockers.length > 0) return;
    startLock.current = true;
    setStarting(true);
    setJobError(null);
    if (requestId.current == null) requestId.current = newRequestId();
    try {
      const result = await api.startCopyJob({
        source_start: sourceStart,
        weeks,
        target_start: target,
        client_request_id: requestId.current,
      });
      if (!mounted.current) return;
      surfaceJob(result.job, result.items);
      await advanceUntilPaused(result.job.job_id);
    } catch (cause: unknown) {
      if (mounted.current) {
        setJobError(copyError(cause));
        loadOpenJobs();
      }
    } finally {
      startLock.current = false;
      if (mounted.current) setStarting(false);
    }
  };

  const resume = async (next: CopyJob) => {
    if (advancing || starting) return;
    setResuming(next.job_id);
    setJobError(null);
    try {
      const current = await api.copyJob(next.job_id);
      if (!mounted.current) return;
      surfaceJob(current.job, current.items);
      await advanceUntilPaused(next.job_id);
    } catch (cause: unknown) {
      if (mounted.current) setJobError(copyError(cause));
    } finally {
      if (mounted.current) setResuming(null);
    }
  };

  const sourceEnd = addDays(sourceStart, weeks * 7 - 1);
  const targetEnd = addDays(target, weeks * 7 - 1);
  const readyCount =
    preview?.items.filter((item) => item.status === "ready").length ?? 0;
  const existing = preview?.existing_target_count ?? 0;
  const canStart =
    online &&
    preview != null &&
    preview.blockers.length === 0 &&
    readyCount > 0 &&
    !previewLoading &&
    !starting &&
    !advancing &&
    job == null;

  const terminal =
    job != null && ["completed", "partial", "failed"].includes(job.state);

  return (
    <Sheet crumb="Woche kopieren" label="Woche kopieren" onClose={onClose}>
      <p className="add-workout__eyebrow">Kopie</p>
      <h1 className="add-workout__title">
        {weeks === 1 ? "Woche kopieren" : "Block kopieren"}
      </h1>
      <p className="add-workout__date">
        {fmtDateLong(sourceStart)} – {fmtDateLong(sourceEnd)}
      </p>

      {!online && (
        <p className="copy-week__notice" role="status">
          Offline — die Vorschau kann geladen werden, kopiert wird erst mit
          Verbindung.
        </p>
      )}

      {openJobs.length > 0 && job == null && (
        <section className="copy-week__open" aria-labelledby="copy-open-title">
          <h2 id="copy-open-title">Offene Kopie</h2>
          <p>
            Ein früherer Kopiervorgang ist noch nicht abgeschlossen. Er wird
            ausschließlich lesend geprüft und dann fortgesetzt.
          </p>
          {openJobs.map((open) => (
            <div key={open.job_id} className="copy-week__open-row">
              <span>
                {fmtDateLong(open.source_start)} · {open.created}/{open.total}{" "}
                angelegt
                {open.unknown > 0 ? ` · ${open.unknown} unklar` : ""}
              </span>
              <button
                type="button"
                className="btn btn--ghost"
                disabled={resuming != null || advancing}
                onClick={() => void resume(open)}
              >
                {resuming === open.job_id ? "Wird geprüft…" : "Fortsetzen"}
              </button>
            </div>
          ))}
        </section>
      )}
      {openJobsError && (
        <p className="copy-week__error" role="alert">
          {openJobsError}
        </p>
      )}

      {job == null && (
        <>
          <section className="copy-week__fields" aria-label="Kopierumfang">
            <div className="copy-week__row">
              <div>
                <span className="copy-week__label">Quellwoche</span>
                <strong>{fmtDateLong(sourceStart)}</strong>
              </div>
              <StatusBadge>Vorausgewählt</StatusBadge>
            </div>

            <div className="copy-week__row">
              <div>
                <label className="copy-week__label" htmlFor="copy-target">
                  Zielwoche
                </label>
                <input
                  id="copy-target"
                  className="plan-input"
                  type="date"
                  value={target}
                  onChange={(event) => changeTarget(event.target.value)}
                />
              </div>
              <span className="copy-week__hint">
                Standard: {fmtDateLong(addDays(sourceStart, 7 * weeks))}
              </span>
            </div>

            <button
              type="button"
              className="copy-week__multi-toggle"
              aria-expanded={multiOpen}
              onClick={() => {
                const next = !multiOpen;
                setMultiOpen(next);
                changeWeeks(next ? Math.max(2, weeks) : 1);
              }}
            >
              <span aria-hidden="true">{multiOpen ? "−" : "+"}</span>
              Mehrere Wochen kopieren
            </button>

            {multiOpen && (
              <div className="copy-week__weeks">
                <span className="copy-week__label">Anzahl Wochen</span>
                <div className="copy-week__segments" role="group" aria-label="Anzahl Wochen">
                  {WEEK_COUNTS.map((count) => (
                    <button
                      key={count}
                      type="button"
                      className={`copy-week__segment${
                        weeks === count ? " copy-week__segment--active" : ""
                      }`}
                      aria-pressed={weeks === count}
                      onClick={() => changeWeeks(count)}
                    >
                      {count}
                    </button>
                  ))}
                </div>
                <p className="copy-week__hint">
                  {fmtDateLong(sourceStart)} – {fmtDateLong(sourceEnd)} werden
                  auf {fmtDateLong(target)} – {fmtDateLong(targetEnd)} gelegt.
                </p>
              </div>
            )}
          </section>

          <section className="copy-week__preview" aria-labelledby="copy-preview-title">
            <h2 id="copy-preview-title">Vorschau</h2>
            {previewLoading && <p className="copy-week__hint">Vorschau wird geprüft…</p>}
            {previewError && (
              <div className="copy-week__error" role="alert">
                <p>{previewError}</p>
                <button
                  type="button"
                  className="btn btn--ghost"
                  onClick={() => setPreviewNonce((value) => value + 1)}
                >
                  Erneut prüfen
                </button>
              </div>
            )}
            {preview && (
              <>
                <div className="copy-week__coverage">
                  <span>Quelle: {preview.coverage.source === "covered" ? "vollständig" : preview.coverage.source}</span>
                  <span>Ziel: {preview.coverage.target === "covered" ? "vollständig" : preview.coverage.target}</span>
                </div>

                {preview.blockers.length > 0 && (
                  <ul className="copy-week__blockers" role="alert">
                    {preview.blockers.map((blocker) => (
                      <li key={`${blocker.code}-${blocker.date ?? ""}`}>
                        <strong>{blocker.message}</strong>
                      </li>
                    ))}
                  </ul>
                )}

                {existing > 0 && (
                  <p className="copy-week__notice" role="status">
                    {existing === 1
                      ? "Am Zieltag liegt bereits eine Planung. Sie bleibt unverändert."
                      : `Am Ziel liegen bereits ${existing} Planungen. Sie bleiben unverändert.`}
                  </p>
                )}

                {preview.items.length === 0 ? (
                  <p className="copy-week__hint">
                    In der Quellwoche liegen keine offenen Planungen.
                  </p>
                ) : (
                  <ul className="copy-week__items">
                    {preview.items.map((item) => (
                      <li
                        key={`${item.source_event_id}-${item.target_date}`}
                        className={`copy-week__item copy-week__item--${item.status}`}
                      >
                        <div>
                          <strong>{item.name}</strong>
                          <span>{previewItemMeta(item)}</span>
                        </div>
                        <div className="copy-week__item-side">
                          <span>{fmtDateLong(item.target_date)}</span>
                          {item.status === "already_copied" && (
                            <StatusBadge>Bereits übernommen</StatusBadge>
                          )}
                          {item.status === "blocked" && (
                            <span className="copy-week__item-blocked">
                              {item.reason ?? "Nicht kopierbar"}
                            </span>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}

                <p className="copy-week__total">
                  {readyCount} {readyCount === 1 ? "Einheit" : "Einheiten"} werden
                  kopiert
                  {preview.totals.already_copied > 0
                    ? ` · ${preview.totals.already_copied} bereits übernommen`
                    : ""}
                  .
                </p>
              </>
            )}
          </section>
        </>
      )}

      {job != null && (
        <section className="copy-week__job" aria-labelledby="copy-job-title">
          <div className="copy-week__job-head">
            <div>
              <h2 id="copy-job-title">{JOB_STATE_LABEL[job.state]}</h2>
              <p>{job.message}</p>
            </div>
            <span className=" copy-week__job-count">
              {job.created}/{job.total}
            </span>
          </div>
          <div
            className="copy-week__progress"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={job.total}
            aria-valuenow={job.created + job.failed + job.unknown}
            aria-label="Fortschritt der Kopie"
          >
            <span
              style={{
                width: `${job.total === 0 ? 0 : ((job.created + job.failed + job.unknown) / job.total) * 100}%`,
              }}
            />
          </div>
          {jobError && (
            <p className="copy-week__error" role="alert">
              {jobError}
            </p>
          )}
          <ul className="copy-week__items">
            {items.map((item) => (
              <li
                key={item.item_id}
                className={`copy-week__item copy-week__item--${item.state}`}
              >
                <div>
                  <strong>{item.name}</strong>
                  <span>
                    {fmtDateLong(item.target_date)} · {ITEM_STATE_LABEL[item.state]}
                  </span>
                  {item.message && <span>{item.message}</span>}
                </div>
                <div className="copy-week__item-side">
                  {item.remote_id && <span>Event {item.remote_id}</span>}
                </div>
              </li>
            ))}
          </ul>
          {advancing && <p className="copy-week__hint">Nächste Einheit wird angelegt…</p>}
          {job.can_advance && !advancing && (
            <div className="copy-week__job-actions">
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => void resume(job)}
              >
                {terminal ? "Unklaren Status prüfen" : "Fortsetzen"}
              </button>
            </div>
          )}
          {terminal && (
            <div className="copy-week__job-actions">
              <button type="button" className="btn btn--ghost" onClick={onClose}>
                Schließen
              </button>
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => {
                  const targetWeek = job.target_start;
                  onClose();
                  onOpenWeek(targetWeek);
                }}
              >
                Zur Zielwoche
              </button>
            </div>
          )}
        </section>
      )}

      {job == null && (
        <div className="copy-week__actions">
          <button
            type="button"
            className="btn btn--ghost"
            onClick={onClose}
            disabled={starting}
          >
            Abbrechen
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!canStart}
            onClick={() => void start()}
          >
            {starting
              ? "Wird vorbereitet…"
              : jobError
                ? "Erneut versuchen"
                : weeks === 1
                  ? "Woche kopieren"
                  : "Block kopieren"}
          </button>
        </div>
      )}
      {jobError && job == null && (
        <p className="copy-week__error" role="alert">
          {jobError}
        </p>
      )}
    </Sheet>
  );
}
