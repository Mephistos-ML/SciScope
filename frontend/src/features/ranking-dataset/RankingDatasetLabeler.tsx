import { useMemo, useState } from "react";

import { saveRankingDatasetRun } from "../../lib/api";
import type { ExploreResultItem } from "../../types/api";

type Label = 0 | 1 | 2;

export function RankingDatasetLabeler({
  searchJobId,
  results,
  labels,
}: {
  searchJobId: string | null;
  results: ExploreResultItem[];
  labels: Record<string, Label>;
}) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const counts = useMemo(() => ({
    golden: Object.values(labels).filter((label) => label === 2).length,
    relevant: Object.values(labels).filter((label) => label === 1).length,
    notRelevant: Object.values(labels).filter((label) => label === 0).length,
  }), [labels]);

  async function save() {
    if (!searchJobId) return;
    setSaving(true);
    setMessage(null);
    try {
      const saved = await saveRankingDatasetRun({ searchJobId, labels });
      setSaved(true);
      setMessage(`Dataset saved: ${saved.candidateCount} candidates, ${saved.labeledCount} labels.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save dataset.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="ranking-dataset-panel">
      <div>
        <p className="section-kicker">Internal beta</p>
        <p className="ranking-dataset-copy">
          {counts.golden} Golden · {counts.relevant} Relevant · {counts.notRelevant} Not relevant · {results.length - Object.keys(labels).length} Unlabeled
        </p>
      </div>
      <button className="outline-button" disabled={!searchJobId || saved || saving || counts.golden === 0} onClick={() => void save()} type="button">
        {saved ? "Dataset saved" : saving ? "Saving dataset..." : "Save dataset"}
      </button>
      {message ? <p className="ranking-dataset-message">{message}</p> : null}
    </section>
  );
}

export function RankingDatasetLabelSelect({
  value,
  onChange,
}: {
  value: Label | undefined;
  onChange: (label: Label | null) => void;
}) {
  return <select aria-label="ML dataset label" onChange={(event) => onChange(event.target.value ? Number(event.target.value) as Label : null)} value={value ?? ""}>
    <option value="">Label</option>
    <option value="2">Golden — 2</option>
    <option value="1">Relevant — 1</option>
    <option value="0">Not relevant — 0</option>
  </select>;
}
