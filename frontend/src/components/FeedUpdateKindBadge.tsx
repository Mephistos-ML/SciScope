// SPDX-FileCopyrightText: 2026 Ernest Borysenko
// SPDX-License-Identifier: Apache-2.0

import type { FeedGroupItem } from "../types/api";

export function FeedUpdateKindBadge({ kind }: { kind: FeedGroupItem["kind"] }) {
  return <span className={`feed-update-kind-badge${kind === "commits" ? " feed-update-kind-badge-commits" : ""}`}>
    {kind === "release" ? "Release" : "Commits"}
  </span>;
}
