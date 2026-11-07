# AI Journal

## User Instructions

1. Create an empty Python project that can use:
   - NumPy
   - pandas
   - seaborn
   - scikit-learn (the requested `sk-lean`)
   - statistical tools through `scipy.stats` (the requested `stats`)

2. Keep a journal file containing the user's instructions to the AI assistant.
   All AI agents working in this repository must read this journal before
   starting and update it after each project request with the current goal,
   decisions, progress, files changed, and verified results. Keep it useful for
   handing work to another agent; never record credentials or secrets.

3. Prepare one shared folder of reusable procedure files for machine learning,
   hypothesis testing, graphical construction, and related data work.

## Project Decisions

- Project name: `clima`
- Python requirement: `>=3.10`
- Development environment: `.venv`
- Dependency management: `pyproject.toml`
- Package source directory: `src/clima`

## Current Work

### 2026-11-07 — GBIF Switzerland SQL download

- The user is exploring GBIF occurrence data for Switzerland and wants to
  select the downloaded attributes instead of receiving all fields.
- The previous implementation used the public paginated
  `/v1/occurrence/search` endpoint, which returns the full record schema and
  cannot project fields.
- Current changes replace that flow with GBIF's asynchronous SQL occurrence
  download and add `src/util/gbif_svizzera.sql`, listing all 432 fields from
  GBIF's SQL schema one per line, each with a short description in a SQL
  comment. Eleven fields are active by default; comment or uncomment a line to
  change the selection.
- `src/util/gbif_svizzera.py` now reads the SQL template, submits the request,
  polls for completion, downloads the ZIP, and loads its TSV into a DataFrame.
  GBIF credentials are expected in environment variables or the project's
  ignored `.env` file.
- `jupyter_prototyping.ipynb` instructions were updated to explain SQL
  downloads and credential setup.
- Root `AGENTS.md` requires all AI agents working in the project to read and
  maintain this journal so they share project context.
- Local checks passed for all 432 documented columns, the 11 default selected
  columns, toggling a column, the row-limit guard, Python compilation, notebook
  JSON, and `git diff --check`.
- Status: the code has not been validated against a completed authenticated
  GBIF SQL download. The SQL validation endpoint returned HTTP 404 in an
  unauthenticated probe; test the actual download with user GBIF credentials
  before claiming end-to-end success.
- The user encountered the expected missing-credentials error before a
  download was submitted. The helper loads `.env` from the repository root;
  clarify that the returned DataFrame is in notebook memory and is not
  automatically written to disk. The runtime error and notebook instructions
  now include the exact credential-file location and optional CSV save example.
- The project `.env` exists and defines `GBIF_USER` and `GBIF_PWD`, not the
  longer variable names previously required. The downloader now accepts both
  naming conventions; secret values were not printed or recorded. Confirmed
  locally that dotenv resolves both credential values and Python/notebook
  syntax checks pass. An authenticated GBIF download has not yet been run.
- The user reports the SQL call is taking a long time. The SQL download is
  asynchronous and the previous polling loop emitted no progress output.
  Added download-key and periodic status/elapsed-time messages, and clarified
  in the notebook that the row limit does not promise a fast server-side query.
  The already-running notebook call uses its existing loaded code; progress
  messages will appear only when it is run again with the updated module.
- User requested keeping both download modes under separate names. The module
  now exposes `scarica_gbif_svizzera_sql` for asynchronous configurable-column
  SQL downloads and `scarica_gbif_svizzera_ricerca` for the public paginated
  search API with a row limit and all record fields. The notebook defaults to
  the search API (no GBIF credentials) and documents how to call the SQL
  variant; the stale SQL-running output was cleared. A mocked pagination test
  verified three-page retrieval for 650 rows (`300 + 300 + 50`) and the
  100,000-row cap. Both functions and notebook references were verified;
  Python compilation, notebook JSON, and `git diff --check` pass. Neither
  external API flow has been verified end-to-end in this environment.
- User requested passing SQL directly as a function argument and a notebook
  call example. `scarica_gbif_svizzera_sql` accepts `sql=...`, while retaining
  the external SQL template as the default; a supplied trailing `LIMIT` is
  replaced by `limite_righe`. The notebook includes and invokes an editable SQL
  query example, restricted to Switzerland, species, and records with
  coordinates. A mocked submission verified payload/query-limit handling and
  invalid-query checks; no live GBIF SQL request was made.
