# Catalog Profile Repair

The repair command defaults to a read-only preview, makes provider requests,
and returns JSON with before/after fields. Run it inside the configured backend
environment:

```sh
python -m scripts.repair_repository_profiles --dry-run --limit 100
```

Default selection targets profiles whose metadata contains
`query`, with empty owner, description, language, topics and provider timestamp,
and zero stars. This is a candidate signal, not proof of corruption. Legitimately
sparse profiles without that signature are skipped. To inspect a specific catalog
record regardless of that signature, use `--repository-id` (repeatable).

After reviewing the preview, apply only the selected IDs:

```sh
python -m scripts.repair_repository_profiles --apply --repository-id github:repo:123
```

The default cap is 100 provider lookups. Catalog reads use ID-ordered pages of
at most 100 profiles; explicit IDs are also queried in batches of at most 100.
The eligibility check runs before counting against the provider cap, so finding
candidates can require scanning the catalog. This bounds each database read and
retained profile data, rather than the total number of rows examined. Existing
explicit IDs beyond the cap are left unprocessed; only absent IDs are reported
as missing.

Run reports classify each selected profile
as `would_update`, `updated`, `unchanged`, `skipped_changed`, or `failed`. Apply
uses a conditional update against the revision read before fetching the provider:
a concurrent catalog update is preserved and reported as `skipped_changed`.
Provider errors are isolated per profile. Exit code 1 indicates failed or skipped
profiles; review the report before retrying. Repository IDs, subscriptions,
query evidence, monitoring cursors and historical Feed events are preserved.
If semantic catalog retrieval is enabled, run the semantic backfill after repair
to refresh changed embeddings.

See the [backend overview](../../backend/README.md) for catalog ownership.
