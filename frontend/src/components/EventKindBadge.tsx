type EventKindBadgeProps = {
  kind: string;
};

const EVENT_KIND_LABELS: Record<string, string> = {
  commit: "Commit",
  release: "Release",
};

export function EventKindBadge({ kind }: EventKindBadgeProps) {
  const normalizedKind = kind.trim().toLowerCase();
  const label = EVENT_KIND_LABELS[normalizedKind] ?? kind;
  const toneClass = normalizedKind === "commit" ? " event-kind-badge-commit" : "";

  return <span className={`event-kind-badge${toneClass}`}>{label}</span>;
}
