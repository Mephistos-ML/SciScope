# Repository ranking

## Owner and score

`backend/app/services/search/ranking/` owns scoring and its typed result models.
Its public entrypoint is `rank_repository_candidates`; `features.py` owns evidence
counting, and `score.py` owns location weights and the calculation:

`score = sum(location_weight * ln(1 + distinct_match_count))`.

Initial weights are name 1.00, description 0.85, topic 0.75, README 0.65,
documentation 0.55, code 0.60, other 0.25, and metadata fallback 0.65. They are
provisional policy values, not learned relevance probabilities.

`score.py` constructs the per-location breakdown once per candidate; ranking
orchestration sums those contributions for the score. Final visibility is owned
by `explore.canonical.select_canonical_candidates`, which combines admission with
the score threshold. `RankingResult` carries only the sorted candidates;
`ExploreSearchEvaluation` owns the validated visibility threshold. The ranker
does not accept a threshold or expose a separate visibility projection.

Scores are nonnegative, retain full floating-point precision, and have no fixed
upper bound. Sorting is descending by score, then case-folded title, then
canonical repository ID. Rounding belongs to display. Query position, alignment,
origin, provider rank, channel, raw hit count, and historical queries do not
contribute directly to the score.

## Match identity and limits

Within one repository, one distinct observed match is identified by:

1. query normalized by case-folding and whitespace collapse;
2. assigned match location;
3. file path with backslashes normalized to slashes and outer whitespace removed.

File paths retain case. Empty path denotes an observation without file identity.
Only evidence for the current operation's executed query set counts. The same
query/location/path delivered again by a provider, retry, channel, or local
catalog counts once. Different queries count separately, including reformulations
matching the same file. Raw evidence is retained for diagnostics and is not the
distinct match count.

Providers currently expose repository/file hits, not a stable identifier for
every occurrence inside a file. Multiple occurrences in the same file for the
same query therefore count once; no local word-frequency inference is performed.
Distinct file paths count separately. A path-bearing hit is classified by its
file location before inspecting repository metadata. Without a path, classification
tries name, description, topic, then the channel fallback. Metadata is a fallback
observation, not an extra match added to an already classified field.

Provider result/page limits and missing evidence censor these counts. Zero
observed matches does not establish complete absence of relevant content.
The formula does not correct for differences in provider coverage or query count.
Future span-level counting requires a separate evidence contract and persistence
plan rather than interpreting historical hits as occurrence counts.

## Visibility and explicit configuration

Admission still governs candidate eligibility. The additional score filter is
`score >= score_threshold`. Composition reads and validates
`EXPLORE_SEARCH_LOG_MATCH_CUTOFF` and supplies it through `ExploreDependencies` to
initial, partial, and expanded search evaluation. It must be finite and
nonnegative. The default is 0, disabling additional score-based exclusion while
the new threshold is being evaluated; even an admitted zero-score candidate can
therefore be visible. This is a delivery-policy change from the old cutoff of 50.

The retired `EXPLORE_SEARCH_RELEVANCE_CUTOFF` setting causes startup to fail if
nonempty. It cannot silently carry a 0--100 threshold onto the new scale.

## Serialized contracts and historical data

New public result items include `scoreFormula: location_weighted_log_matches_v1`.
Historical response payloads may omit this field and keep their delivered scores.
New run creation records this policy version. An existing run retains its
creation-time policy metadata; if expanded after deployment, its new stage is
evaluated using the new formula. Each stage's score breakdown identifies the
policy that actually produced it.

New ranking breakdown JSON has `schema_version: 3`, `formula`, and `locations`,
where each location has `location`, `count`, `weight`, and unrounded `contribution`.
Ranking features contain `match_counts_by_location`, `raw_hit_count`, and
`evidence_record_count` alongside query diagnostics. Counts of raw deliveries and
retained evidence records are distinct from the deduplicated scoring counts.
The UI labels query coverage as "Matched queries"; this fraction is not Recall.

Historical version-2 breakdowns retain `points`; their features retain
`location_counts`, `hit_count`, and `evidence_count`. Unversioned historical
breakdowns retain strongest-match/corroboration fields. The diagnostic UI reads
all three representations without rewriting history. This is a representation
change only: the scoring policy identifier and numeric formula are unchanged.

Internal provenance and admission contracts use `raw_hit_count`. Durable catalog
observation counts keep their existing `hit_count` storage contract, and resumable
execution JSON keeps its existing `hitCount` key with an explicit mapping to the
renamed application field. No database or execution-state migration is needed.
There is no table migration or backfill. Resumable retrieval evidence retains
its existing schema and is recounted on subsequent evaluation. Counting uses the
public `retrieval.evidence.classify_match_path` contract to classify path-bearing
evidence, including historical hits previously labeled by overlapping metadata.
Raw stored evidence stays unchanged; old/new deliveries of the same file cannot
count twice merely because their original location labels differ.

## Validation and quality

Regression checks cover location weights, count saturation and monotonicity,
query/file deduplication, current-query scope, deterministic ranking, cutoff
validation, provider-file classification, and serialized/UI score explanations.
The arithmetic and behavioral comparison is recorded in
[`benchmarks/research/ranking-change-evaluation.md`](../../benchmarks/research/ranking-change-evaluation.md).
These checks do not establish improved retrieval relevance on real user queries;
held-out benchmark evaluation remains required before claiming that improvement.
