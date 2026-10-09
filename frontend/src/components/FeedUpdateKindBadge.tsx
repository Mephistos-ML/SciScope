import type { FeedGroupItem } from "../types/api";

export function FeedUpdateKindBadge({ kind }: { kind: FeedGroupItem["kind"] }) {
  return <span className={`feed-update-kind-badge${kind === "commits" ? " feed-update-kind-badge-commits" : ""}`}>
    {kind === "release" ? "Release" : "Commits"}
  </span>;
}
