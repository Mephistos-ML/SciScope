# Optional scientific domain

`app.models.scientific_domain.ScientificDomain` owns the eight stable domain IDs:
`physics`, `chemistry`, `materials_science`, `biology_bioinformatics`,
`earth_environmental_science`, `astronomy_space_science`,
`mathematics_statistics`, and `computer_science`.

Both Explore search POST bodies accept optional `scientificDomain`. Omission or
JSON null means no supplied domain. Empty strings, unknown IDs and non-string
values return HTTP 422 before admission or scheduling. The existing question
text is preserved; domain selection does not change quota policy or its topic
hash. Generated TypeScript declarations derive the vocabulary from the domain
owner, and OpenAPI describes the nullable enum.

For background searches, `search_runs.scientific_domain` is the authoritative,
immutable choice for the entire run, including queued work and expansions.
Snapshots and diagnostic run reports expose `scientificDomain` as an ID or null,
independently of historical response JSON. Old rows remain null; stored reports
and execution-state schemas are not rewritten. Clients accept an absent field
when communicating with older servers.

The contract currently records context only. Connecting it to query generation
and exposing the selector are separate changes; no domain filtering is applied
to repository search. Selecting a domain must not be presented as affecting
retrieval until the planner consumes it.

## Deployment and recovery

Revision `0019_search_scientific_domain` adds one nullable column with no data
backfill or default. Apply the migration before deploying the new backend.
Old binaries can keep writing rows with null while the schema is expanded.
Database DDL still takes a table lock; schedule the migration accordingly.

Do not enable domain selection until all API and worker instances understand the
field and the planner consumes it. An old worker could otherwise execute a run
without its selected context. Application rollback may retain the extra column;
downgrading the schema drops saved domain choices, so preserve a backup before
that destructive operation. No production migration is performed by development
tests.
