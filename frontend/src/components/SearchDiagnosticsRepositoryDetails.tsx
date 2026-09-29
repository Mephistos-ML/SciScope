import type { SearchDiagnosticsRankingSnapshot } from "../types/api";

type SearchDiagnosticsRepositoryDetailsProps = {
  snapshot: SearchDiagnosticsRankingSnapshot;
};

type MatchEvidence = {
  query: string;
  location: string;
  path: string | null;
  alignment: number | null;
  channel: string | null;
  origin: string | null;
  retrievalRank: number | null;
};

export function SearchDiagnosticsRepositoryDetails({
  snapshot,
}: SearchDiagnosticsRepositoryDetailsProps) {
  const features = snapshot.rankingFeatures;
  const admission = snapshot.admissionFacts;
  const retrieval = snapshot.retrievalFacts;
  const scoreBreakdown = snapshot.scoreBreakdown;
  const matchedQueryCount = readNumber(features, "matched_query_count");
  const totalQueryCount = readNumber(features, "total_query_count");
  const evidenceCount = readNumber(features, "evidence_count");
  const hitCount = readNumber(features, "hit_count");
  const evidence = readMatchEvidence(retrieval.match_evidence);

  return (
    <section className="repository-diagnostics-details">
      <div className="repository-diagnostics-header">
        <div>
          <p className="section-kicker">Internal ranking</p>
          <h4>Ranking details</h4>
        </div>
        <div className="repository-diagnostics-score">
          <span>Backend rank #{snapshot.rankPosition}</span>
          <strong>{formatScore(snapshot.finalScore)}</strong>
        </div>
      </div>

      <div className="repository-diagnostics-metrics">
        <Metric
          label="Query coverage"
          value={formatRatio(matchedQueryCount, totalQueryCount)}
        />
        <Metric label="Evidence" value={formatCount(evidenceCount, "items")} />
        <Metric label="Raw hits" value={formatCount(hitCount, "hits")} />
        <Metric label="Admission" value={formatLabel(readString(admission, "decision") ?? "unknown")} />
      </div>

      <div className="repository-diagnostics-columns">
        <section>
          <h5>Score breakdown</h5>
          <dl className="repository-diagnostics-definition-list">
            <Definition
              label="Strongest match"
              value={formatPoints(readNumber(scoreBreakdown, "strongest_match_points"))}
            />
            <Definition
              label="Corroboration"
              value={formatPoints(readNumber(scoreBreakdown, "corroboration_points"))}
            />
            <Definition
              label="Strongest quality"
              value={formatDecimal(readNumber(features, "strongest_match_quality"))}
            />
            <Definition
              label="Corroboration quality"
              value={formatDecimal(readNumber(features, "corroboration_quality"))}
            />
          </dl>
        </section>

        <section>
          <h5>Retrieval context</h5>
          <dl className="repository-diagnostics-definition-list">
            <Definition label="Origins" value={formatList(readStringList(retrieval.origins))} />
            <Definition label="Channels" value={formatList(readStringList(retrieval.matched_channels))} />
            <Definition label="Admission bucket" value={formatLabel(readString(admission, "bucket") ?? "unknown")} />
          </dl>
        </section>
      </div>

      <section className="repository-diagnostics-evidence">
        <h5>Match evidence</h5>
        {evidence.length ? (
          <ul>
            {evidence.map((item, index) => (
              <li key={`${item.query}-${item.channel ?? ""}-${item.location}-${item.path ?? ""}-${index}`}>
                <strong>{item.query}</strong>
                <span>{formatLabel(item.location)}</span>
                {item.channel ? <span>Channel {formatLabel(item.channel)}</span> : null}
                {item.origin ? <span>Origin {formatLabel(item.origin)}</span> : null}
                {item.retrievalRank !== null ? (
                  <span>Retrieval rank #{item.retrievalRank}</span>
                ) : null}
                {item.path ? <code>{item.path}</code> : null}
                {item.alignment !== null ? <span>Alignment {formatDecimal(item.alignment)}</span> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p>No match evidence was recorded.</p>
        )}
      </section>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="repository-diagnostics-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Definition({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function readNumber(value: Record<string, unknown>, key: string): number | null {
  const candidate = value[key];
  return typeof candidate === "number" && Number.isFinite(candidate) ? candidate : null;
}

function readString(value: Record<string, unknown>, key: string): string | null {
  const candidate = value[key];
  return typeof candidate === "string" && candidate.trim() ? candidate : null;
}

function readStringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.trim() !== "")
    : [];
}

function readMatchEvidence(value: unknown): MatchEvidence[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const candidate = item as Record<string, unknown>;
    const query = readString(candidate, "query");
    const location = readString(candidate, "location");
    if (!query || !location) return [];
    return [{
      query,
      location,
      path: readString(candidate, "path"),
      alignment: readNumber(candidate, "alignment"),
      channel: readKnownString(candidate, "channel"),
      origin: readKnownString(candidate, "origin"),
      retrievalRank: readNumber(candidate, "retrieval_rank"),
    }];
  });
}

function readKnownString(value: Record<string, unknown>, key: string): string | null {
  const candidate = readString(value, key);
  return candidate && candidate !== "unknown" ? candidate : null;
}

function formatScore(value: number): string {
  return `${value.toFixed(2)} / 100`;
}

function formatRatio(numerator: number | null, denominator: number | null): string {
  if (numerator === null || denominator === null) return "—";
  return `${numerator} / ${denominator}`;
}

function formatCount(value: number | null, noun: string): string {
  if (value === null) return "—";
  return `${value} ${noun}`;
}

function formatPoints(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(2)} pts`;
}

function formatDecimal(value: number | null): string {
  return value === null ? "—" : value.toFixed(2);
}

function formatList(value: string[]): string {
  return value.length ? value.map(formatLabel).join(", ") : "—";
}

function formatLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (character: string) => character.toUpperCase());
}
