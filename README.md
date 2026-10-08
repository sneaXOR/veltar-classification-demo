# Veltar — document classification prototype

Veltar develops export-control document workflows for specialist review. This repository publishes a cleaned snapshot of the existing classification POC: a FastAPI backend, React frontend, document ingestion, source-backed classification stages, deterministic validation and a review queue.

[Product and architecture](https://product.veltar.co) · [Browser intake demo](https://product.veltar.co/demo.html) · [Claude extraction experiment](https://product.veltar.co/evaluation.html)

## What is implemented

- Ingestion of PDFs, images, Office documents, text and email attachments.
- An orchestrator that combines an LLM client with deterministic knowledge-base loading and validation.
- Document-level results, insufficient-evidence handling, review and exports.
- A React interface for upload, document evidence, clients and review.
- Backend tests with mocked inference.

This is a prototype, not a production deployment or a legal/export authorization service. Specialist review remains required.

## Run locally

Python 3.11+ and Node.js 20+ are suitable for the development setup.

```bash
python -m venv .venv
# Activate .venv for your shell, then:
pip install -r backend/requirements.txt
python scripts/generate_demo_corpus.py
python -m pytest backend/tests
```

Start the backend from `backend/`:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Start the frontend from `frontend/`:

```bash
npm ci
npm run dev
```

API: `http://127.0.0.1:8000`; frontend: `http://localhost:3000`.

Docker is an alternative:

```bash
cp compose.env.example compose.env
docker compose up --build
```

The services are bound to localhost in this public snapshot. The app can start without an inference key; live classifications require a configured provider and may incur costs. Keep credentials in local environment files, never frontend code.

## Claude usage and evidence

Claude is used for coding and architecture. The existing application inference client is OpenAI-compatible and defaults to Qwen through OpenRouter; this repository does not claim that its classification pipeline currently calls the direct Anthropic API.

A separate free Claude web experiment on 8 October 2026 extracted four fields from each of three synthetic documents. Local validation found 12/12 expected values and exact source quotations. The missing end user stayed null and an instruction embedded in one document was ignored. The examples were submitted together in one prompt; this small result is not a general reliability benchmark.

Inspect the evidence under [`experiments/claude-intake/`](experiments/claude-intake/), or reproduce the local scoring without an API call:

```bash
python experiments/claude-intake/score_chat.py
```

`evaluate.py` is a prepared direct Anthropic test client. Its default mode is offline. `--live` is optional and consumes credits; no live API evaluation was performed for this publication.

## Snapshot provenance

Copied from the existing private `Veltar-POC-classification` working tree on 8 October 2026. The source's latest commit is dated 13 May 2026; this new public repository does not backdate commits or reproduce private history.

The snapshot excludes secrets, runtime uploads/databases, cached golden-document outputs and internal planning notes. Binary fixtures are regenerated from the included synthetic corpus script. The classifier source and UI come from the existing project; the chat evaluation is separate recent work.

Veltar is bootstrapped, based in Toulouse, and not yet incorporated. Its project start date is not a legal incorporation date.

## Verification of this public snapshot

On 8 October 2026, the backend suite completed with **89 passed and 1 skipped** (Python 3.13). The skipped test requires private cached document outputs that are excluded from this publication. The public test harness uses dummy credentials for mocked inference and explicitly sets French for assertions that depend on French strings; application defaults are unchanged. No paid inference was used.

The React production build passed with `npm ci --ignore-scripts` and `npm run build`. Dependency warnings remain; this is not a security certification.
