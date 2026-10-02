# Official preloaded source

**Universal Declaration of Human Rights**, United Nations General Assembly,
10 December 1948 (resolution 217 A (III)), English, all 30 articles and preamble.

- Publisher/host: United Nations Office of the High Commissioner for Human Rights (OHCHR).
- Original PDF: https://www.ohchr.org/en/UDHR/Documents/UDHR_Translations/eng.pdf
- Official reference: https://www.un.org/en/about-us/universal-declaration-of-human-rights
- Retrieved: 2026-10-02. Eight physical PDF pages; citations use those page numbers.
- The downloaded PDF is unchanged. `manifest.json` records its SHA-256 checksum.

This is the plain declaration text, without illustrations or a copyright notice,
not the separately copyrighted illustrated UN publication. UN official documents
and public information material are generally left in the public domain under
ST/AI/189/Add.9/Rev.2 (Copyright in United Nations publications). The UN Editorial
Manual also describes UN-symbol documents as generally public domain:
https://digitallibrary.un.org/record/605858/files/United_Nations_Editorial_Manual.pdf
This third-party document is attributed to the United Nations; the repository's
MIT license covers the application code, not a claim of authorship over UN text.

Run `uv run python -m scripts.seed_graph` from `backend/` with the intended
Neo4j and Redis configuration. The script uses the real extraction and embedding
pipeline; answers and citations are generated from indexed passages. No answers
are hardcoded. Once the declaration is fully indexed, it becomes the public
sample and the former fictional examples are unpinned. Visitor uploads remain.
Rerunning reuses a completely indexed copy without more embedding calls.
