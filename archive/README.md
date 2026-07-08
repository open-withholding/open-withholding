# /archive

Local staging area for retrieved source PDFs, keyed by sha256
(`<sha256>.pdf` + `<sha256>.json` retrieval metadata). Written by
`pipeline/extract.py`; referenced from each data file's `source.sha256`.

Contents are gitignored — this directory is **not** the durable archive.
Per DESIGN.md §8.4 the durable home is an immutable bucket or a separate
`sources-archive` repo, to be set up before the first data release; until
then, keep local copies and don't clean this directory. The citation is only
auditable if the exact bytes we extracted from are retained (agencies replace
and delete PDFs); government publications are public domain, so
redistribution is fine.
