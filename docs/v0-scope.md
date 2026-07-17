# SciScope V0 Scope

## Goal

Build an end-to-end proof of concept for SciScope that ingests a small set of pNMR-relevant sources, normalizes them into a single signal schema, and displays them in a dashboard.

## First Users

- Me
- My supervisor
- My partner

## V0 Niche

- Paramagnetic NMR (`pNMR`)

## V0 Sources

- ChemRxiv
- GitHub
- One curated community source

## What Counts As A Signal

A signal is a newly discovered item that may matter to a narrow research topic, such as:

- preprint
- software release
- workshop or conference update
- lab or community announcement

## LLM Usage In V0

- Used for `topic -> research profile`
- Not used for ranking
- Not used for source parsing

## Seeded Development Profile

- First seeded topic: `pnmr`
- First seeded repository focus: `Mephistos-ML/paranmr`
- First success case: detect a relevant Paranmr GitHub patch from a manual profile

## V0 Output

- Dashboard first
- Digest later

## Non-Goals

- Universal multi-domain quality
- Full user authentication
- Billing and subscriptions
- Complex ranking
- LinkedIn ingestion

## Success Criteria

- A topic can be created for pNMR
- A research profile can be generated
- Three sources can be ingested into one schema
- Known relevant signals appear in the dashboard
