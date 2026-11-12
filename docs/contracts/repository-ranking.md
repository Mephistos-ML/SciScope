# Repository ranking

## Owner and score

`backend/app/services/search/ranking/` owns scoring and its typed result models.
Its public entrypoint is `rank_repository_candidates`; `features.py` owns evidence
counting, and `score.py` owns location weights and the calculation:

`match_score = sum(location_weight * ln(1 + distinct_match_count))`.

The final score adds an optional bounded popularity contribution:

`score = match_score + alpha * min(1, ln(1 + stars) / ln(1 + reference_stars))`.

Initial weights are name 1.00, description 0.85, topic 0.75, README 0.65,
documentation 0.55, code 0.60, and metadata fallback 0.65. Notebook, data,
configuration, project metadata, legal, and other each initially use 0.25. They are
provisional policy values, not learned relevance probabilities.

`score.py` constructs the per-location breakdown once per candidate; ranking
orchestration sums the location and popularity contributions for the score. Final visibility is owned
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

### File taxonomy and precedence (ranking policy v2)

Rules use case-insensitive names/extensions and normalized separators, without
reading file contents or inferring unreported matches. Apply them in this order:

1. Explicit legal names (`LICENSE`, `LICENCE`, `COPYING`, `NOTICE`, `COPYRIGHT`,
   with optional document/TXT suffixes) and project manifests/citation files
   (`pyproject.toml`, `setup.py`, `package.json`, `CITATION.cff`, dependency
   lockfiles, requirements TXT files, and environment YAML manifests).
2. Recognized README names.
3. Files in `doc/`, `docs/`, or `documentation/` directories.
4. Notebooks (`.ipynb`, `.qmd`, `.Rmd`).
5. Recognized source-code extensions.
6. Configuration (`Dockerfile`, `Dockerfile.*`, `compose.json`, YAML, TOML, INI,
   CFG, CONF, and properties files) excluding the manifests already classified.
7. Data formats (CSV, TSV, Parquet, HDF5, FITS, NetCDF, NumPy arrays, XYZ, PDB,
   SDF, MOL/MOL2, CIF).
8. Other recognized documentation: Markdown, reStructuredText, AsciiDoc, and
   named documents such as CHANGELOG/CONTRIBUTING, including their TXT forms.
9. `other` for an unrecognized path or an unidentified non-repository-search hit.

For example, `docs/tutorial.ipynb` is documentation; `docs/LICENSE` is legal;
`pyproject.toml` is project metadata; `examples/input.yaml` is configuration.
Arbitrary JSON/XML/TXT files remain `other` because extension alone does not
identify their role. File categories identify observed evidence, not intrinsic
relevance or whether a repository should pass admission.

Taxonomy expansion is policy `location_weighted_log_matches_v2`. The logarithmic
formula is unchanged, but splitting one count across categories changes its
aggregate score even with equal weights. Do not combine v1 and v2 evaluations
without recording the policy. Path-bearing cached/v1 evidence is reclassified
when scored; original stored evidence and completed reports remain unchanged.

## Visibility and explicit configuration

### Popularity parameters (ranking policy v3)

Composition supplies immutable `PopularityBoostParameters` through Explore
dependencies to initial, partial, and expanded evaluations. `max_bonus` is alpha,
a finite nonnegative cap in score units; `reference_stars` is a fixed positive
integer determining saturation.

Deployment settings are `EXPLORE_RANKING_POPULARITY_MAX_BONUS` (default 0) and
`EXPLORE_RANKING_POPULARITY_REFERENCE_STARS` (default 1000). Alpha 0 preserves
match-only numeric scores. The reference is a provisional scale, not a measured
optimum. Select both parameters on development data, freeze them before testing,
and record them with every run. Adding candidates must not rescale other scores.

Normalized popularity lies in [0, 1], and its contribution cannot exceed alpha.
It cannot reverse a match-score gap strictly larger than alpha. This is an
additive model: when enabled, stars can contribute even without current-query
matches. Admission remains independent; the visibility threshold applies to the
final score, including this bonus. Re-evaluate nonzero thresholds.

At the feature boundary, stars must be a nonnegative integer; missing/invalid
values contribute zero and are recorded as unavailable (`null`). A known zero
remains zero. Existing adapters may already encode unavailable stars as zero;
the ranker cannot reconstruct information lost upstream. GitHub and GitLab
distributions need separate evaluation. Current candidate merging retains the
larger observed count, which can preserve a stale catalog value after a decrease;
this change does not claim freshness correction. Popularity is not a probability
or relevance label.

### Output selection

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

New public result items include `scoreFormula: location_weighted_log_matches_v3`.
Historical log-match items may identify v1 or v2 of that scoring policy.
Historical response payloads may omit this field and keep their delivered scores.
New run creation records this policy version. An existing run retains its
creation-time policy metadata; if expanded after deployment, its new stage is
evaluated using the new formula. Each stage's score breakdown identifies the
policy that actually produced it.

New ranking breakdown JSON has `schema_version: 4`, `formula`, `locations`, and `popularity`,
where each location has `location`, `count`, `weight`, and unrounded `contribution`.
Ranking features contain `match_counts_by_location`, `raw_hit_count`, and
`evidence_record_count`, and `stars` alongside query diagnostics. The popularity
breakdown records stars, reference_stars, max_bonus, normalized_popularity, and
contribution, so delivered scores remain reproducible after configuration changes.
Counts of raw deliveries and
retained evidence records are distinct from the deduplicated scoring counts.
The UI labels query coverage as "Matched queries"; this fraction is not Recall.

Historical version-3 breakdowns contain named location contributions without a
popularity object. Historical version-2 breakdowns retain `points`; their features retain
`location_counts`, `hit_count`, and `evidence_count`. Unversioned historical
breakdowns retain strongest-match/corroboration fields. The diagnostic UI reads
all four representations without rewriting history. This is a representation
change only between breakdown schemas 2 and 3; taxonomy versions are identified
independently by the scoring policy field.

Internal provenance and admission contracts use `raw_hit_count`. Durable catalog
observation counts keep their existing `hit_count` storage contract, and resumable
execution JSON keeps its existing `hitCount` key with an explicit mapping to the
renamed application field. The taxonomy extension writes execution schema 2 and
explicitly reads/upgrades schema 1; see the
[execution-state contract](explore-execution-state.md). No table migration or bulk
backfill is needed. Match-evidence fields retain their shape while execution
schema 2 extends their allowed vocabulary. Evidence is recounted on subsequent
evaluation. Counting uses the
public `retrieval.evidence.classify_match_path` contract to classify path-bearing
evidence, including historical hits previously labeled by overlapping metadata.
Raw stored evidence stays unchanged; old/new deliveries of the same file cannot
count twice merely because their original location labels differ.

Popularity uses existing repository metadata in the execution payload; execution
schema 2 is unchanged. Completed responses stay immutable. A resumed/expanded
evaluation uses the configured parameters and stored or newly retrieved stars,
recording the resulting policy and contributions per stage.

## Validation and quality

Regression checks cover location weights, count saturation and monotonicity,
query/file deduplication, current-query scope, deterministic ranking, cutoff
validation, provider-file classification, and serialized/UI score explanations.
The arithmetic and behavioral comparison is recorded in
[`benchmarks/research/ranking-change-evaluation.md`](../../benchmarks/research/ranking-change-evaluation.md).
These checks do not establish improved retrieval relevance on real user queries;
held-out benchmark evaluation remains required before claiming that improvement.
