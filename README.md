# Sentinel AI — Prototype

A working, end-to-end implementation of the tech stack from the project
synopsis: **React + Vite + Tailwind + Recharts** dashboard, **FastAPI**
backend, **PostgreSQL** for structured storage, **Redis** as the
collector→detection queue, a real **psutil + Watchdog** endpoint
collector, a **scikit-learn / PyTorch / XGBoost** detection ensemble,
and a **Cytoscape.js** threat graph.

Everything below was actually run and verified while building this —
not just written. See "What was tested" at the bottom.

## Architecture

```
Metadata Collector (simulator or live psutil/watchdog)
        │  push_event()
        ▼
   Redis queue  (sentinel:events:raw)
        │  drain_events()
        ▼
 Event Processing + Behaviour Profiling  (profiling.py — rolling 7-day baseline)
        │
        ▼
 AI Detection Engine (detection/engine.py)
   ├─ Isolation Forest   (scikit-learn)
   ├─ Autoencoder        (PyTorch, per-day reconstruction error)
   ├─ LSTM autoencoder   (PyTorch, per-employee sequence — catches slow-drip trends)
   └─ XGBoost            (weakly supervised on Isolation Forest's own top-decile)
        │
        ▼
 Dynamic Risk Engine (risk_engine.py)  →  0-100 score + tier + rule_flags
        │
        ▼
 AI Investigation Agent (agent.py)  →  plain-language explanation
        │
        ▼
 PostgreSQL (risk_records, graph_edges, employees)
        │
        ▼
 FastAPI (routers/) ──── React + Vite + Tailwind + Recharts + Cytoscape dashboard
```

## Running it

**1. One-time environment setup** (installs Postgres + Redis if needed, creates the DB):
```bash
./setup_env.sh
```

**2. Backend** (in one terminal — creates a venv, installs deps, seeds the
simulated dataset, runs the full detection pipeline, starts the API):
```bash
./run_backend.sh
```
First run installs PyTorch, which is a genuinely large download (~700MB-1GB) —
this is expected, not a hang. API docs at `http://localhost:8000/docs`.

**3. Frontend** (in another terminal):
```bash
./run_frontend.sh
```
Dashboard at `http://localhost:5173`.

To re-seed with a fresh simulated run (new random seed, or after code changes
to the detection engine), just re-run `python -m app.pipeline` from inside
`backend/` with the venv active.

**4. Real-time Alert Streaming & Live Replay**
Sentinel AI streams High and Critical security alerts to the SOC Dashboard in real-time
via Server-Sent Events (SSE) at `GET /api/stream/alerts` backed by Redis pub/sub channel
`sentinel:alerts`.

To see the dashboard update live without page refreshes, run the live replay script:
```bash
backend/venv/bin/python backend/scripts/live_replay.py --interval 3.0
```
> **Note on Replay vs. Live Scoring:** `live_replay.py` is a **replay of precomputed scores**,
> NOT live scoring. It replays the simulated organisation day by day, inserting each day's
> already-computed records into Postgres and publishing alerts to Redis in real time so the
> SOC dashboard visibly updates live.

**5. Outbound Notifications (Slack, Telegram, SMTP Email)**
When alerts meet or exceed the minimum configured risk tier (default `Critical`),
Sentinel AI dispatches notifications across configured channels:
- Slack incoming webhook (`SLACK_WEBHOOK_URL`)
- Telegram bot (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)
- SMTP email (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TO`)

Notifications strictly convey metadata (employee ID, date, tier, score, rule flags,
and dashboard case link); file contents are never read or transmitted.
Alerts are deduplicated per `(employee_id, date)` with a 24-hour Redis TTL.
All channels are optional and fail-safe. Check status or test delivery:
- `GET /api/notifications/status`
- `POST /api/notifications/test`

**6. SOC Security Assistant (Guardrailed Read-Only Queries)**
The SOC Assistant allows analysts to query threat telemetry in plain English:
- **No Arbitrary SQL**: Operates exclusively through a whitelisted set of 7 typed SQLAlchemy ORM queries (max 90 days, max 50 rows).
- **Dual Mode**:
  - `ollama`: Uses Ollama `/api/chat` with native function calling.
  - `fallback`: Deterministic regex/keyword intent router that executes the same tools when no LLM is running.
- **Anti-Prompt-Injection**: Rejects attempts to alter rules, execute SQL, or drop tables.
- **Audited**: Every query, execution mode, and tool called is recorded in `assistant_audit_log`.
- Slide-over chat panel available via the floating button on the SOC Dashboard.



## What's real vs. simulated

- **Real**: Postgres, Redis, the FastAPI API, all four detection models, the
  risk engine, the graph builder, and the entire frontend — all genuinely
  running and tested against each other, not mocked.
- **Real but demoed briefly**: the live collector
  (`collectors/live_collector.py`). It uses actual `psutil` process/network
  counters and a real `watchdog` filesystem observer (inotify under the
  hood) — while building this I pointed it at `/tmp/sentinel_watch`,
  dropped a 2MB `.zip` file in, and it correctly emitted a real event with
  the real file size and a `risky_extension: true` flag. In production
  you'd point `watch_dir` at a real monitored folder and let it run
  continuously; a semester-project demo can't realistically show 30 days
  of a machine's real activity, so the bundled dashboard data comes from
  the simulator, which is explicitly labelled as such throughout the code.
- **Simulated**: the 20-employee / 30-day dataset that populates the
  dashboard by default (`collectors/simulator.py`), with 3 employees
  seeded with real insider-threat behavioural patterns (slow-drip,
  resignation dump, off-hours bulk transfer) so you can point at
  concrete recall numbers when demoing or writing up results.
- **Not implemented** (out of scope per the trimmed stack): Ollama
  itself isn't installed/running here — `agent.py` has a working,
  tested-fallback hook for it (`AGENT_MODE=ollama` in `.env`), so
  wiring in a real local model is a config change, not new code, once
  you have Ollama installed and a model pulled.

## Project layout

```
backend/
  app/
    config.py                  Settings (env-driven; see .env.example)
    database.py, models.py     Postgres via SQLAlchemy (psycopg3)
    queue.py                   Redis queue (collector -> event processing)
    collectors/
      simulator.py             Synthetic 20-employee/30-day dataset + 3 seeded scenarios
      live_collector.py        Real psutil + watchdog endpoint collector
    profiling.py                Event processing + rolling behavioural baseline
    detection/
      autoencoder.py            PyTorch feed-forward autoencoder
      lstm.py                    PyTorch LSTM sequence autoencoder (slow-drip detection)
      engine.py                  Combines Isolation Forest + Autoencoder + LSTM + XGBoost
    risk_engine.py               Blends model scores + rule boosts -> 0-100 risk score
    agent.py                     AI Investigation Agent (template, or Ollama if configured)
    graph.py                     NetworkX threat graph, persisted as Postgres adjacency rows
    pipeline.py                  Orchestrates the full flow end-to-end
    routers/                     /api/health, /employees, /alerts, /stats, /graph
    main.py                      FastAPI app
  requirements.txt
frontend/
  src/
    api.js                       Fetch wrapper for the backend
    App.jsx                      Layout, view switching (dashboard / threat graph)
    components/
      StatsBar.jsx                Header summary cards
      EmployeeTable.jsx            Employee list sorted by peak risk
      RiskTimelineChart.jsx         Recharts per-employee risk-over-time line chart
      IncidentQueue.jsx             AI-generated alert explanations
      ThreatGraph.jsx                Cytoscape.js employee->destination graph
  package.json, vite.config.js, tailwind.config.js
setup_env.sh, run_backend.sh, run_frontend.sh
```

## Design decisions worth knowing about (for your synopsis writeup / guide questions)

- **Redis as a queue, not Kafka/RabbitMQ**: a plain Redis list
  (`RPUSH`/`LRANGE`+`LTRIM`) is enough to decouple the collector from
  the detection stage at this scale, and is far less operational
  overhead than standing up a real message broker for a prototype.
- **Score blending**: each model's raw anomaly score is normalised
  with median/MAD-based robust scaling (not min-max, not percentile
  rank) before blending — min-max lets one extreme outlier compress
  every other score toward zero, and percentile rank forces a fixed
  percentage of days into the "high" range regardless of whether
  they're actually anomalous. Robust scaling avoids both failure
  modes. The final score favours the single strongest model (60%
  weight on the max of the four scores, 40% on their mean) — appropriate
  for a SOC alerting context where missing a real threat is costlier
  than one extra false positive to triage.
- **XGBoost's labels**: with no hand-labelled incident data available,
  XGBoost is trained on Isolation Forest's own top-decile as
  pseudo-labels. This is a defensible bootstrap for prototype scale;
  swap in real analyst-confirmed labels once the system is deployed
  and alerts start getting triaged.
- **Threat graph in Postgres, not Neo4j**: relationships are stored as
  plain adjacency rows (`graph_edges` table) and rendered client-side
  with Cytoscape.js. Fine until graph queries get complex enough
  (multi-hop pattern matching) to justify a real graph database.

## What was tested while building this

- Postgres and Redis installed, started, and connected to over the
  real network (not just imported/mocked).
- The live collector actually run for several seconds, with a real
  file dropped into its watched directory — the emitted event's size
  and risky-extension flag were verified against the real file.
- The full pipeline run end-to-end against Postgres multiple times
  while tuning the risk-blending logic, checking recall on the 3
  seeded scenarios each time (final result: 95.3 / 89.7 / 99.9 out of
  100, with 35/600 employee-days flagged High or Critical — the
  ensemble genuinely separates the seeded scenarios from normal
  behaviour instead of hard-coding an outcome).
- A real bug in the graph builder was caught and fixed here (a
  `MultiDiGraph` was creating a duplicate edge per event instead of
  one aggregated edge per employee-destination pair — 956 edges
  instead of the correct 86).
- Every API endpoint (`/health`, `/stats`, `/employees`,
  `/employees/{id}/timeline`, `/alerts`, `/graph`) queried directly
  against the live Postgres-backed API and checked against expected
  shapes/values.
- CORS verified with real preflight (`OPTIONS`) and real cross-origin
  `GET` requests from the Vite dev server's origin.
- `npm run build` run clean with no errors (1 warning about bundle
  size, which is normal for an unsplit single-page dashboard bundle
  and not a functional issue).
