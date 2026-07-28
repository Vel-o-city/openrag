# Seed documents

Three short documents that give the public demo something to explore before
anyone uploads anything.

**These are fiction.** Every person, organisation, place and project named here
was invented for this repository. Nothing in them is a claim about anything
real — which is the point: the demo runs an LLM over these documents and
asserts what it extracts, and a public site shouldn't do that to real people.

They are original work by the repository owner and carry the repo's MIT
licence. That rules out the licensing question a found corpus would raise —
Wikipedia is CC BY-SA, whose share-alike terms would reach into an MIT repo,
and Project Gutenberg texts are public domain but too entity-sparse to build a
legible graph from.

## Why three, and why they overlap

The seed set is built to show off the thing the ingestion pipeline is actually
clever about: **the same entity appearing in different documents resolves to
one node instead of three.** People, organisations and places recur across all
three documents, so the seeded graph is genuinely interconnected rather than
three disjoint clusters.

Observed on a real ingestion run, which is worth recording because it also
shows where resolution stops:

| Written as | Result |
| --- | --- |
| `Meridian Labs`, `Meridian` | merged — one node, via token-subset match |
| `Halden Institute`, `Lisbon`, `Priya Raghunathan` | merged — one node each, spanning all three documents |
| `Dr. Amara Okonkwo`, `A. Okonkwo` | **not merged** — two nodes |
| `the Kepler Initiative` | **not merged** — three nodes, one per extracted type |

Both non-merges are the resolver behaving as written, not bugs introduced here:

- `a okonkwo` vs `dr amara okonkwo` fails token-subset and scores 72 on fuzzy
  ratio against an 85 threshold. `app/graph/entity_resolution.py` says up front
  that it biases toward creating a new entity over an uncertain merge, on the
  grounds that a false split is cosmetic while a false merge corrupts
  information. An initial-only alias is exactly the uncertain case it declines.
- `resolve_or_create_entity` filters its candidate shortlist by entity-type
  label, so a name extracted once as an `Organization` and once as a `Concept`
  is never even considered for merging.

Keep this table honest if the resolver changes — it doubles as a regression
check, and its value depends on it describing what actually happens.

## Regenerating the PDFs

`sources/*.md` is the text; the PDFs are generated from it and committed so
seeding is deterministic and doesn't depend on a rendering toolchain.

```bash
cd backend
uv run --with reportlab python scripts/build_seed_pdfs.py
```

Then load them into a running local stack with `uv run python scripts/seed_graph.py`.
