import { useEffect, useState } from "react";

import {
  fetchSignalDetail,
  fetchSignals,
  fetchStatus,
  startScan,
  stopScan,
} from "../lib/api";
import { formatLastScan } from "../lib/formatters";
import type {
  SignalDetailPayload,
  SignalListItem,
  StatusPayload,
} from "../types/api";
import { MetricCard } from "../components/MetricCard";
import { SourceBadge } from "../components/SourceBadge";

type LoadState = "idle" | "loading" | "syncing" | "error";
type DetailState = "idle" | "loading" | "ready" | "error";

export function DashboardPage() {
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [signals, setSignals] = useState<SignalListItem[]>([]);
  const [selectedSignalId, setSelectedSignalId] = useState<string | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<SignalDetailPayload | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [detailState, setDetailState] = useState<DetailState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [startPending, setStartPending] = useState(false);
  const [stopPending, setStopPending] = useState(false);

  async function loadDashboard(mode: LoadState = "loading") {
    setLoadState(mode);
    setErrorMessage(null);

    try {
      const [nextStatus, nextSignals] = await Promise.all([
        fetchStatus(),
        fetchSignals(),
      ]);
      setStatus(nextStatus);
      setSignals(nextSignals.items);

      if (nextSignals.items.length === 0) {
        setSelectedSignalId(null);
        setSelectedSignal(null);
        setDetailState("idle");
      } else if (
        selectedSignalId === null ||
        !nextSignals.items.some((signal) => signal.itemId === selectedSignalId)
      ) {
        setSelectedSignalId(nextSignals.items[0].itemId);
      }

      setLoadState("idle");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unexpected frontend error.";
      setErrorMessage(message);
      setLoadState("error");
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  useEffect(() => {
    if (!status?.autoScanStarted) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void loadDashboard("syncing");
    }, 5000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [status?.autoScanStarted]);

  useEffect(() => {
    if (selectedSignalId === null) {
      return;
    }

    const signalId = selectedSignalId;
    let cancelled = false;

    async function loadSignalDetail() {
      setDetailState("loading");

      try {
        const detail = await fetchSignalDetail(signalId);
        if (cancelled) {
          return;
        }
        setSelectedSignal(detail);
        setDetailState("ready");
      } catch (error) {
        if (cancelled) {
          return;
        }
        const message =
          error instanceof Error ? error.message : "Failed to load signal detail.";
        setErrorMessage(message);
        setDetailState("error");
      }
    }

    void loadSignalDetail();

    return () => {
      cancelled = true;
    };
  }, [selectedSignalId]);

  async function handleStart() {
    setStartPending(true);
    setErrorMessage(null);

    try {
      await startScan();
      await loadDashboard("syncing");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to start scan.";
      setErrorMessage(message);
      setLoadState("error");
    } finally {
      setStartPending(false);
    }
  }

  async function handleStop() {
    setStopPending(true);
    setErrorMessage(null);

    try {
      await stopScan();
      await loadDashboard("syncing");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to stop scan.";
      setErrorMessage(message);
      setLoadState("error");
    } finally {
      setStopPending(false);
    }
  }

  const lastScan = formatLastScan(status?.lastScanAt ?? null);
  const monitoringState = status?.autoScanStarted ? "on" : "off";
  const autoScanStarted = status?.autoScanStarted ?? false;
  const discoveryStatus = status?.lastDiscoveryError
    ? "error"
    : status?.lastDiscoveryResult
      ? "ready"
      : "idle";

  return (
    <main className="page-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Scientific signal monitoring</p>
          <h1>SciScope</h1>
          <p className="hero-copy">
            Narrow-field research radar for signals that usually get missed.
          </p>
        </div>
        <div className="hero-actions">
          <button
            className="primary-button"
            onClick={() => void handleStart()}
            disabled={startPending || stopPending || autoScanStarted}
          >
            {startPending ? "Starting..." : "Start"}
          </button>
          <button
            className="secondary-button"
            onClick={() => void handleStop()}
            disabled={startPending || stopPending || !autoScanStarted}
          >
            {stopPending ? "Stopping..." : "Stop"}
          </button>
        </div>
      </section>

      <section className="status-grid">
        <MetricCard label="Topic" value={status?.topicSlug ?? "pnmr"} />
        <MetricCard label="Last scan" value={lastScan} />
        <MetricCard
          label="Matched signals"
          value={status ? `${status.matchedSignals} / ${status.totalSignals}` : "0 / 0"}
        />
        <MetricCard label="Monitoring" value={monitoringState} />
      </section>

      {status?.lastScanError ? (
        <section className="warning-banner">
          <strong>Scan warning:</strong> {status.lastScanError}
        </section>
      ) : null}

      {errorMessage ? (
        <section className="error-banner">
          <strong>Frontend error:</strong> {errorMessage}
        </section>
      ) : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="panel-kicker">Dashboard</p>
            <h2>{status?.topicLabel ?? "Paramagnetic NMR"}</h2>
          </div>
          <span className="panel-status">
            {loadState === "loading"
              ? "loading"
              : loadState === "syncing"
                ? "syncing"
                : loadState === "error"
                  ? "error"
                  : "ready"}
          </span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Source</th>
                <th>Kind</th>
                <th>Score</th>
                <th>Match</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {signals.length === 0 ? (
                <tr>
                  <td colSpan={6} className="empty-state">
                    No signals yet. Start the scan and wait for a matching release.
                  </td>
                </tr>
              ) : (
                signals.map((signal) => (
                  <tr
                    key={signal.itemId}
                    className={signal.itemId === selectedSignalId ? "selected-row" : undefined}
                  >
                    <td>
                      <button
                        className="link-button"
                        onClick={() => setSelectedSignalId(signal.itemId)}
                        type="button"
                      >
                        {signal.title}
                      </button>
                    </td>
                    <td>
                      <SourceBadge source={signal.source} />
                    </td>
                    <td>{signal.signalKind}</td>
                    <td>{signal.score.toFixed(1)}</td>
                    <td>
                      <span
                        className={signal.matched ? "badge matched" : "badge not-matched"}
                      >
                        {signal.matched ? "matched" : "not matched"}
                      </span>
                      {signal.isNew ? <span className="badge new">new</span> : null}
                    </td>
                    <td>{signal.reason}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="panel-kicker">Debug</p>
            <h2>Pipeline state</h2>
          </div>
          <span className="panel-status">{discoveryStatus}</span>
        </div>

        <div className="detail-grid">
          <article className="detail-card">
            <p className="detail-label">Last discovery</p>
            <strong>{formatLastScan(status?.lastDiscoveryAt ?? null)}</strong>
          </article>
          <article className="detail-card">
            <p className="detail-label">Discovery queries</p>
            <strong>{status?.discoveryQueries.length ?? 0}</strong>
          </article>
          <article className="detail-card">
            <p className="detail-label">Watched entities</p>
            <strong>{status?.watchedEntities.length ?? 0}</strong>
          </article>
          <article className="detail-card">
            <p className="detail-label">Checkpoints</p>
            <strong>{status?.sourceCheckpoints.length ?? 0}</strong>
          </article>

          <section className="detail-block">
            <h3>Discovery queries</h3>
            <div className="tag-row">
              {status?.discoveryQueries.length ? (
                status.discoveryQueries.map((query) => (
                  <span className="badge debug" key={query}>
                    {query}
                  </span>
                ))
              ) : (
                <span className="muted-text">No discovery queries recorded yet.</span>
              )}
            </div>
          </section>

          <section className="detail-block">
            <h3>Watched entities</h3>
            {status?.watchedEntities.length ? (
              <div className="debug-list">
                {status.watchedEntities.map((entity) => (
                  <article className="debug-item" key={entity.entityId}>
                    <div className="debug-item-header">
                      <strong>{entity.repo ?? entity.entityId}</strong>
                      <SourceBadge source={entity.source} />
                    </div>
                    <span>{entity.language ?? "unknown language"}</span>
                    <span>{entity.stars ?? 0} stars</span>
                    <span>query: {entity.query ?? "n/a"}</span>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted-text">No watched entities yet.</p>
            )}
          </section>

          <section className="detail-block">
            <h3>Source checkpoints</h3>
            {status?.sourceCheckpoints.length ? (
              <div className="debug-list">
                {status.sourceCheckpoints.map((checkpoint) => (
                  <article className="debug-item" key={checkpoint.entityId}>
                    <div className="debug-item-header">
                      <strong>{checkpoint.repo ?? checkpoint.entityId}</strong>
                      <SourceBadge source={checkpoint.source} />
                    </div>
                    <span>{checkpoint.checkpointValue ?? "no checkpoint yet"}</span>
                    <span>{checkpoint.updatedAt ?? "not updated"}</span>
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted-text">No checkpoints yet.</p>
            )}
          </section>

          <section className="detail-block">
            <h3>Last discovery result</h3>
            <pre>
              {JSON.stringify(status?.lastDiscoveryResult ?? null, null, 2)}
            </pre>
          </section>
        </div>
      </section>

      <section className="panel detail-panel">
        <div className="panel-header">
          <div>
            <p className="panel-kicker">Signal detail</p>
            <h2>{selectedSignal?.title ?? "Select a signal"}</h2>
          </div>
          <span className="panel-status">{detailState}</span>
        </div>

        {selectedSignal === null ? (
          <p className="empty-detail">
            Pick a signal from the table to inspect why it matched.
          </p>
        ) : (
          <div className="detail-grid">
            <article className="detail-card">
              <p className="detail-label">Source</p>
              <strong>
                <SourceBadge source={selectedSignal.source} />
              </strong>
            </article>
            <article className="detail-card">
              <p className="detail-label">Kind</p>
              <strong>{selectedSignal.signalKind}</strong>
            </article>
            <article className="detail-card">
              <p className="detail-label">Score</p>
              <strong>{selectedSignal.score.toFixed(1)}</strong>
            </article>
            <article className="detail-card">
              <p className="detail-label">URL</p>
              <strong>
                <a href={selectedSignal.url} target="_blank" rel="noreferrer">
                  Open source
                </a>
              </strong>
            </article>

            <section className="detail-block">
              <h3>Reason</h3>
              <p>{selectedSignal.reason}</p>
            </section>

            <section className="detail-block">
              <h3>Matched terms</h3>
              <div className="tag-row">
                {selectedSignal.matchedTerms.length === 0 ? (
                  <span className="muted-text">No matched terms.</span>
                ) : (
                  selectedSignal.matchedTerms.map((term) => (
                    <span className="badge matched" key={term}>
                      {term}
                    </span>
                  ))
                )}
              </div>
            </section>

            <section className="detail-block">
              <h3>Excluded terms</h3>
              <div className="tag-row">
                {selectedSignal.excludedTerms.length === 0 ? (
                  <span className="muted-text">No excluded terms.</span>
                ) : (
                  selectedSignal.excludedTerms.map((term) => (
                    <span className="badge not-matched" key={term}>
                      {term}
                    </span>
                  ))
                )}
              </div>
            </section>

            <section className="detail-block">
              <h3>Raw text</h3>
              <pre>{selectedSignal.rawText}</pre>
            </section>

            <section className="detail-block">
              <h3>Normalized text</h3>
              <pre>{selectedSignal.normalizedText}</pre>
            </section>
          </div>
        )}
      </section>

    </main>
  );
}
