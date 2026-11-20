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

## Query planning

`services.ai.search_plans.format_search_plan_topic` owns the application policy
for rendering context. It passes the planner `Scientific domain: <label>`, a blank
line, then the original question. Its label mapping is a natural-language planner
representation, separate from persisted IDs. Without a supplied domain, the
planner receives the same question text as before; no domain is inferred.

Both synchronous searches and initial background operations use this path.
Workers read the immutable domain from the durable run, including after a queued
operation is reclaimed. The raw question remains the input for admission, topic
hashing and response presentation. Catalog retrieval still consumes generated
queries, so domain context can affect its candidates indirectly as well.
Expansions use the saved plan and do not regenerate queries or accept a
replacement domain.

The OpenAI adapter's default is the reviewed Entity anchor system prompt. The
first query anchors on the shortest distinctive entity or specific concept
stated in the question; the remaining two use complementary established phrases.
Domain context disambiguates terminology rather than mandating a query prefix or
suffix. The response contract remains three nonempty, unique queries of at most
185 characters each. Word-count guidance is a prompt instruction, not a new hard
parser limit.

Generated queries feed the existing retrieval channels. Domain is not a provider
filter, and repository-search channels are not disabled by this change. Existing
completed plans and reports are not regenerated when the default prompt changes.

## Explore selector

Explore displays an optional native select alongside the question on desktop,
stacked beneath it on smaller screens. Its IDs come from the generated backend
vocabulary; display labels belong to the UI. The initial choice is Not specified,
sent as null. The control has a visible label, keyboard support and the existing
field focus styles.

The choice lives with the question draft in App state. New searches submit it
as `scientificDomain`; loading temporarily disables the selector. Errors and
completed searches preserve the draft choice. Editing it applies to a new search,
while expansion uses the existing run's immutable domain and does not overwrite
the draft. Like the question draft, it is not persisted in browser storage across
a page reload.

The prompt was selected in offline quoted GitHub code-search experiments. Those
results do not establish retrieval quality for the combined production channels
or the broader domain labels; product acceptance evaluates that composition
separately.

## Deployment and recovery

Revision `0019_search_scientific_domain` adds one nullable column with no data
backfill or default. Apply the migration before deploying the new backend.
Old binaries can keep writing rows with null while the schema is expanded.
Database DDL still takes a table lock; schedule the migration accordingly.

Do not enable domain selection until all API and worker instances understand the
field and the planner consumes it. An old worker could otherwise execute a run
without its selected context. The new frontend sends `scientificDomain` even
when null; old API binaries reject that field. Deploy the compatible API and
workers before exposing this selector. If the ranking reader must also be
upgraded first, deploy both frontend and backend while traffic is quiesced for
the existing coordinated cutover, then reopen traffic. No runtime capability
detection or old-server fallback is implemented.

Application rollback may retain the extra column;
downgrading the schema drops saved domain choices, so preserve a backup before
that destructive operation. No production migration is performed by development
tests.
