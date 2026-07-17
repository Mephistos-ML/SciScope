# Source Inventory

## V0 Sources

### ChemRxiv

- source type: structured feed or listing
- target signal kinds: preprint
- required fields: title, url, published_at, abstract or summary text

### GitHub

- source type: API or curated repository feed
- target signal kinds: software release, repository update
- required fields: title, url, published_at, release notes or description

### Curated Community Source

- source type: selected workshop, conference, lab, or community page
- target signal kinds: workshop, announcement, community update
- required fields: title, url, published_at when available, raw text

## Source Adapter Contract

Every adapter should return a raw source item with:

- source name
- source type
- external id when available
- title
- url
- published_at
- raw text

The adapter must not decide final relevance. It only fetches and normalizes the
source payload into the shared raw signal shape.

## Notes

- LinkedIn is intentionally excluded from V0
- Additional regional and community sources belong to later versions
