import type {
  SearchDiagnosticsProviderOutcome,
  SearchDiagnosticsReport,
  SearchDiagnosticsStage,
} from "../types/api";

type SearchDiagnosticsSummaryProps = {
  report: SearchDiagnosticsReport;
};

export function SearchDiagnosticsSummary({ report }: SearchDiagnosticsSummaryProps) {
  const latestStage = report.stages[report.stages.length - 1] ?? null;
  const executedQueries = [...new Set(report.stages.flatMap((stage) => stage.executedQueries))];
  const summaryMessage = buildSummaryMessage(report);

  return (
    <section className="info-panel search-diagnostics-panel">
      <div className="search-diagnostics-header">
        <div>
          <p className="section-kicker">Internal</p>
          <h2 className="panel-title">Search diagnostics</h2>
        </div>
        <span className={`search-diagnostics-status search-diagnostics-status-${report.run.status}`}>
          {formatRunStatus(report.run.status)}
        </span>
      </div>

      {summaryMessage ? <p className="search-diagnostics-message">{summaryMessage}</p> : null}

      {latestStage ? <RunSnapshot latestStage={latestStage} stageCount={report.stages.length} /> : null}

      <details className="search-diagnostics-details" open>
        <summary>Run details</summary>
        <div className="search-diagnostics-details-content">
          <section className="search-diagnostics-section">
            <h3>AI planner</h3>
            <p className="search-diagnostics-empty">
              {formatPlannerConfiguration(report.run.plannerMode, report.run.plannerModel, report.run.plannerReasoningEffort)}
            </p>
          </section>

          <section className="search-diagnostics-section">
            <h3>Executed queries</h3>
            {executedQueries.length ? (
              <div className="query-chip-row search-diagnostics-query-chip-row">
                {executedQueries.map((query) => (
                  <span className="query-chip" key={query}>{query}</span>
                ))}
              </div>
            ) : (
              <p className="search-diagnostics-empty">No search queries were executed.</p>
            )}
          </section>

          <section className="search-diagnostics-section">
            <h3>Provider outcomes</h3>
            {report.providerOutcomes.length ? (
              <div className="search-diagnostics-outcomes-table">
                <div className="search-diagnostics-outcomes-head">
                  <span>Stage</span>
                  <span>Source</span>
                  <span>Channel</span>
                  <span>Status</span>
                  <span>Candidates</span>
                  <span>Time</span>
                  <span>Details</span>
                </div>
                <div className="search-diagnostics-outcomes-body">
                  {report.providerOutcomes.map((outcome, index) => (
                    <ProviderOutcomeRow
                      key={`${outcome.stageNumber}-${outcome.source}-${outcome.channel}-${outcome.query}-${index}`}
                      outcome={outcome}
                    />
                  ))}
                </div>
              </div>
            ) : (
              <p className="search-diagnostics-empty">No provider outcomes were recorded.</p>
            )}
          </section>

          {latestStage ? (
            <section className="search-diagnostics-section">
              <h3>Latest-stage timing</h3>
              <div className="search-diagnostics-timings">
                {Object.entries(latestStage.timings).map(([name, durationMs]) => (
                  <div className="search-diagnostics-timing" key={name}>
                    <span>{formatTimingName(name)}</span>
                    <strong>{formatDuration(durationMs)}</strong>
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      </details>
    </section>
  );
}

function RunSnapshot({ latestStage, stageCount }: { latestStage: SearchDiagnosticsStage; stageCount: number }) {
  const { candidateCounts } = latestStage;
  return (
    <div className="search-diagnostics-metrics">
      <Metric
        label="Candidate funnel"
        value={`${candidateCounts.retrieved} → ${candidateCounts.admitted} → ${candidateCounts.visible}`}
        detail="Retrieved → admitted → visible"
      />
      <Metric label="Stages" value={`${stageCount}`} detail={`Latest: stage ${latestStage.stageNumber}`} />
      <Metric
        label="Latest stage"
        value={formatDuration(latestStage.timings.stage_wall_time ?? 0)}
        detail="Wall-clock duration"
      />
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="search-diagnostics-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function ProviderOutcomeRow({ outcome }: { outcome: SearchDiagnosticsProviderOutcome }) {
  const details = formatOutcomeDetails(outcome);
  return (
    <div className="search-diagnostics-outcome-row">
      <span>{outcome.stageNumber}</span>
      <span>{formatSource(outcome.source)}</span>
      <span>{formatLabel(outcome.channel)}</span>
      <span className={`search-diagnostics-outcome-status search-diagnostics-outcome-status-${outcome.status}`}>
        {formatLabel(outcome.status)}
      </span>
      <span>{outcome.candidateCount}</span>
      <span>{formatDuration(outcome.durationMs)}</span>
      <span>{details ?? "—"}</span>
    </div>
  );
}

function formatOutcomeDetails(outcome: SearchDiagnosticsProviderOutcome): string | null {
  const retryAfter = formatRetryAfter(outcome.retryAfterSeconds);
  if (!outcome.errorMessage) return retryAfter;
  return retryAfter ? `${outcome.errorMessage} ${retryAfter}.` : outcome.errorMessage;
}

function buildSummaryMessage(report: SearchDiagnosticsReport): string | null {
  if (report.run.errorMessage) return report.run.errorMessage;
  if (report.run.partial) return "Search completed with partial provider coverage.";
  return null;
}

function formatRunStatus(status: string): string {
  if (status === "completed_partial") return "Completed with partial coverage";
  return formatLabel(status);
}

function formatTimingName(value: string): string {
  return formatLabel(value).replace("Ai", "AI");
}

function formatSource(value: string): string {
  return value === "github" ? "GitHub" : value === "gitlab" ? "GitLab" : formatLabel(value);
}

function formatPlannerConfiguration(
  mode: string,
  model: string | null,
  reasoningEffort: string | null,
): string {
  if (!model) return `Mode: ${formatLabel(mode)}`;
  return reasoningEffort
    ? `${model} · reasoning: ${reasoningEffort}`
    : model;
}

function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (character: string) => character.toUpperCase());
}

function formatDuration(durationMs: number): string {
  if (durationMs < 1000) return `${durationMs} ms`;
  const seconds = durationMs / 1000;
  return seconds < 10 ? `${seconds.toFixed(1)} s` : `${Math.round(seconds)} s`;
}

function formatRetryAfter(retryAfterSeconds: number | null): string | null {
  if (retryAfterSeconds === null) return null;
  if (retryAfterSeconds < 60) return `Retry in ${retryAfterSeconds}s`;
  const minutes = Math.floor(retryAfterSeconds / 60);
  const seconds = retryAfterSeconds % 60;
  return seconds ? `Retry in ${minutes}m ${seconds}s` : `Retry in ${minutes}m`;
}
