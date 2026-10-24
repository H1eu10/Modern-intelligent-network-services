# Лабораторная работа № 2 — Agro Scoring API

Студент: Фам Минь Хиеу, МПИ-25-1-2.

## Windows (PowerShell)
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```
Открыть http://127.0.0.1:8000/docs.

## Endpoints
`GET /health`, `POST /predict`, `POST /batch-predict`, `POST /predict-queued`, `GET /queue-status`, `GET /predictions`, `GET /predictions/{request_id}`, `GET /requests/{request_id}/predictions`, `GET /predictions/by-weekday?weekday=monday&page=1&per_page=5`, `POST /demo/seed-weekdays`, `POST /llm/chat`, `POST /predict-with-llm`.

### FarmRequest example
```json
{"farm_id":"FARM-001","region":"Krasnodar","crop_type":"wheat","area_ha":100,"temperature_avg":20,"precipitation_mm":200,"payment_delay_days":10,"previous_defaults":0,"debt":10000}
```

`POST /batch-predict`: `{"items":[ <FarmRequest>, <FarmRequest> ]}` (replace placeholders with JSON objects).

`POST /llm/chat`: `{"prompt":"Привет!","model":"auto","temperature":0.3,"max_tokens":300}`.

## Settings
Optional env vars: `DATABASE_PATH`, `LLM_BASE_URL`, `LLM_TIMEOUT_SECONDS`, `MAX_BATCH_SIZE`, `MAX_BATCH_WAIT_MS`, `QUEUE_MAX_SIZE`, `INFERENCE_TIMEOUT_SECONDS`.

For experiment with timeout: `INFERENCE_TIMEOUT_SECONDS=0.001` before launching (PowerShell: `$env:INFERENCE_TIMEOUT_SECONDS="0.001"`).
For 429 demo: set `QUEUE_MAX_SIZE=1` and send parallel requests.

## QA provenance
`qa_results.json` is a 20-case offline test. It used a **QA-only** sqlite3-to-async compatibility driver because `aiosqlite` was unavailable. The provider `LLM` was mocked. This is not equivalent to production integration verification. `qa_support/` is excluded from normal application imports unless put on `PYTHONPATH` explicitly.

Re-run offline QA (only when true aiosqlite cannot be installed): `python qa_support/run_checks.py`.
After installing the official requirements, validate `/docs` and real LLM endpoints manually and replace placeholders in DOCX with screenshots from real Swagger UI.
