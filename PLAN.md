# Job Applier — Implementation Plan v2

## Goals

- Fully containerized: reproducible on any machine with Docker
- Web UI as the primary interface — no CLI required for day-to-day use
- Claude API as the sole AI backend (no LM Studio dependency)
- Clean separation of concerns: scrape, queue, apply are independent stages
- Production-grade dependency management
- Credentials never baked into the image

---

## Tech Stack

| Concern | Choice | Reason |
|---------|--------|--------|
| Language | Python 3.12 | Latest stable, better typing |
| Dependency mgmt | `uv` + `pyproject.toml` + lockfile | Fast, reproducible, modern |
| Browser automation | Playwright (headless) | Works in Docker, well-maintained |
| AI | Anthropic SDK (`anthropic`) | First-class Claude support, structured outputs |
| Queue/state | SQLite via `aiosqlite` | Zero-infra, portable, persistent |
| Config | Pydantic Settings + `.env` | Type-safe config, env var override |
| Logging | `structlog` | JSON-structured logs, easy to grep/pipe |
| Web framework | FastAPI | Async, WebSocket support, auto OpenAPI docs |
| Frontend | React + Vite (TypeScript) | Component-based, fast HMR in dev |
| UI components | shadcn/ui + Tailwind | Clean, unstyled-by-default, no bloat |
| Real-time updates | WebSockets (FastAPI) | Live scrape/apply progress in the UI |
| Containerization | Docker + Docker Compose | Reproducible, isolated |
| Display (browser) | Xvfb virtual display in container | Enables non-headless mode inside Docker |

---

## Project Structure

```
job-applier/
├── Dockerfile
├── docker-compose.yml
├── docker-compose.override.yml.example   # local overrides (not committed)
├── pyproject.toml                        # deps + tool config
├── uv.lock                               # pinned lockfile
├── .env.example                          # template — commit this
├── .env                                  # actual secrets — gitignored
├── .gitignore
│
├── src/                                  # Python backend
│   ├── __init__.py
│   ├── main.py                           # FastAPI app entrypoint
│   ├── config.py                         # Pydantic Settings
│   │
│   ├── api/                              # FastAPI routers
│   │   ├── jobs.py                       # GET /jobs, PATCH /jobs/:id/status
│   │   ├── scrape.py                     # POST /scrape  (triggers scraper)
│   │   ├── apply.py                      # POST /apply   (triggers applier)
│   │   ├── resume.py                     # POST /resume/upload, GET /resume/parsed
│   │   └── ws.py                         # WS  /ws/log   (live log stream)
│   │
│   ├── scraper/                          # Stage 1: Job discovery
│   │   ├── base.py
│   │   ├── linkedin.py
│   │   ├── indeed.py
│   │   ├── dice.py
│   │   └── monster.py
│   │
│   ├── queue/                            # Stage 2: Persistence
│   │   ├── models.py                     # Job dataclass / DB schema
│   │   └── store.py                      # SQLite read/write
│   │
│   ├── applier/                          # Stage 3: Application submission
│   │   ├── base.py
│   │   ├── linkedin.py
│   │   ├── workday.py
│   │   └── generic.py
│   │
│   ├── ai/                               # Claude integration
│   │   ├── client.py                     # Anthropic SDK wrapper
│   │   ├── prompts.py                    # All system/user prompt templates
│   │   └── decisions.py                 # Typed decision logic (apply/skip/fill/confirm)
│   │
│   ├── resume/
│   │   └── parser.py                    # DOCX → structured ResumeData
│   │
│   └── utils/
│       ├── browser.py                   # Playwright context management
│       ├── rate_limiter.py              # Adaptive delay logic
│       └── logging.py                   # structlog setup + WS log broadcaster
│
├── ui/                                   # React frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── components/
│       │   ├── JobTable.tsx              # Paginated job queue view
│       │   ├── JobRow.tsx                # Single job — status badge, actions
│       │   ├── ScrapePanel.tsx           # Platform checkboxes + Scrape button
│       │   ├── ApplyPanel.tsx            # Platform checkboxes + Apply button
│       │   ├── ResumePanel.tsx           # Upload DOCX, view parsed fields, edit inline
│       │   └── LogStream.tsx             # Live WebSocket log tail
│       ├── hooks/
│       │   ├── useJobs.ts                # fetch + poll job queue
│       │   └── useLogStream.ts           # WS connection for live logs
│       └── types/
│           └── api.ts                    # TypeScript types mirroring backend models
│
├── data/                                # gitignored — runtime state
│   ├── jobs.db
│   ├── resume.docx                       # uploaded via UI, stored here
│   └── sessions/                        # saved browser cookies
│
└── reports/                             # gitignored — session output
```

---

## Docker Architecture

### Strategy

Browser automation in Docker is the main challenge. Two approaches:

| Approach | Pros | Cons |
|----------|------|------|
| **Headless only** | Simple, no display needed | Higher bot detection risk |
| **Xvfb virtual display** | Non-headless browser, lower detection risk | Slightly more complex Dockerfile |

**Decision: Xvfb virtual display.** Job boards (especially LinkedIn) are more aggressive about headless detection. Running a real browser against a virtual framebuffer is the safest default.

### Dockerfile

Two-stage build: frontend compiled first, then served as static files by the FastAPI backend.

```dockerfile
# ── Stage 1: Build React UI ─────────────────────────────────────
FROM node:20-slim AS ui-builder
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build          # outputs to /ui/dist

# ── Stage 2: Python backend + browser ───────────────────────────
FROM python:3.12-slim

# Xvfb + Playwright system deps
RUN apt-get update && apt-get install -y \
    xvfb xauth \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Python deps (cached layer)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Source + compiled UI
COPY src/ ./src/
COPY --from=ui-builder /ui/dist ./src/static/

# Playwright browser
RUN uv run playwright install chromium

# FastAPI serves on :8080, Xvfb on :99
EXPOSE 8080
CMD ["xvfb-run", "--auto-servernum", "--server-args=-screen 0 1280x900x24", \
     "uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### docker-compose.yml

```yaml
version: "3.9"

services:
  job-applier:
    build: .
    env_file: .env
    ports:
      - "8080:8080"               # Web UI accessible at http://localhost:8080
    volumes:
      - ./data:/app/data          # persistent DB, sessions, uploaded resume
      - ./reports:/app/reports    # session output
    environment:
      - DISPLAY=:99
    restart: unless-stopped
```

No separate scraper/applier services needed — the web UI triggers those as background tasks via the API.

---

## Claude API Integration

### Design Principles

1. **Typed inputs/outputs** — every AI call has a Pydantic model for request and response. No raw string parsing.
2. **Structured outputs** via `response_format` / tool use — Claude returns JSON, not prose to regex.
3. **Single client** — one `anthropic.Anthropic` instance, shared across the session.
4. **Prompt templates in one place** — `src/ai/prompts.py`, not scattered across applier code.
5. **Graceful degradation** — each decision has a typed default if Claude fails or times out.

### Decision Types

```python
# src/ai/decisions.py

class ApplyDecision(BaseModel):
    action: Literal["apply", "skip", "save"]
    reason: str

class FormFieldDecision(BaseModel):
    value: str          # empty string = leave blank
    confidence: float   # 0.0–1.0

class CustomAnswerDecision(BaseModel):
    answer: str

class SubmitDecision(BaseModel):
    action: Literal["submit", "review", "cancel"]
    reason: str
```

### Claude Calls

All four decision points use `client.messages.create` with `tools` (tool use) to enforce structured JSON output:

```python
# src/ai/client.py

class AIClient:
    def __init__(self, api_key: str, model: str):
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def should_apply(self, job: JobListing, resume: ResumeData) -> ApplyDecision: ...
    def fill_field(self, label: str, field_type: str, options: list[str], resume_value: str) -> FormFieldDecision: ...
    def answer_question(self, question: str, job: JobListing, resume: ResumeData) -> CustomAnswerDecision: ...
    def confirm_submission(self, application: ApplicationSummary) -> SubmitDecision: ...
```

### Model

Default: `claude-haiku-4-5-20251001` for cost efficiency on high-volume field-filling.
Override to `claude-sonnet-4-6` for the apply/skip decision and submission confirmation where judgment matters.

```env
CLAUDE_API_KEY=sk-ant-...
CLAUDE_DECISION_MODEL=claude-sonnet-4-6
CLAUDE_FILL_MODEL=claude-haiku-4-5-20251001
```

---

## Configuration

### .env.example

```env
# Credentials
LINKEDIN_EMAIL=
LINKEDIN_PASSWORD=
INDEED_EMAIL=
INDEED_PASSWORD=

# Claude
CLAUDE_API_KEY=
CLAUDE_DECISION_MODEL=claude-sonnet-4-6
CLAUDE_FILL_MODEL=claude-haiku-4-5-20251001

# Search
SEARCH_KEYWORDS=SOC analyst,security operations,software engineer
SEARCH_LOCATIONS=Remote,New Jersey
SEARCH_DAYS_BACK=7

# Limits
MAX_APPLICATIONS_PER_DAY=50
DELAY_MIN_SECONDS=10
DELAY_MAX_SECONDS=30

# Resume
RESUME_PATH=/app/resume/resume.docx
```

### src/config.py

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    linkedin_email: str
    linkedin_password: str
    indeed_email: str = ""
    indeed_password: str = ""

    claude_api_key: str
    claude_decision_model: str = "claude-sonnet-4-6"
    claude_fill_model: str = "claude-haiku-4-5-20251001"

    search_keywords: list[str] = ["SOC analyst", "security operations"]
    search_locations: list[str] = ["Remote"]
    search_days_back: int = 7

    max_applications_per_day: int = 50
    delay_min_seconds: int = 10
    delay_max_seconds: int = 30

    resume_path: str = "/app/resume/resume.docx"
    db_path: str = "/app/data/jobs.db"
    sessions_dir: str = "/app/data/sessions"
```

---

## Web UI

The container exposes a single-page app at `http://localhost:8080`. The React frontend talks to the FastAPI backend on the same origin — no CORS config needed.

### Pages / Panels

#### 1. Jobs Queue
- Paginated table of all queued jobs
- Columns: title, company, platform, location, status, date added, applied at
- Status badges: `pending` / `applied` / `skipped` / `failed`
- Per-row actions: mark skip, open job URL, view AI decision reason

#### 2. Scrape
- Checkboxed dropdown for platforms: LinkedIn, Indeed, Dice, Monster (multi-select)
- "Start Scraping" button → fires `POST /scrape` with selected platforms
- Live log stream panel shows real-time progress via WebSocket
- Disabled while a scrape or apply job is running

#### 3. Apply
- Checkboxed dropdown for platforms (same pattern as Scrape)
- Limit field (default: 50)
- Dry-run toggle
- "Start Applying" button → fires `POST /apply`
- Live log stream (same WebSocket panel as Scrape)

#### 4. Resume
- **Upload**: drag-and-drop or file picker, accepts `.docx` only
- **Parsed fields view**: table of every extracted field (name, email, phone, LinkedIn, GitHub, skills, certifications, experience entries, education)
- **Inline editing**: each field is editable — corrections are saved back to a `resume_overrides.json` that takes precedence over the DOCX parse. The override file persists in `data/` so it survives container restarts.
- Re-upload replaces the DOCX and re-parses (overrides are preserved unless the field is explicitly cleared)

### API Endpoints (FastAPI)

```
GET  /jobs                     → paginated job list (status filter, platform filter)
PATCH /jobs/{id}               → update status (skip, reset to pending)
GET  /jobs/stats               → counts by status and platform

POST /scrape                   → { platforms: ["linkedin", "indeed"] }
POST /apply                    → { platforms: [...], limit: 50, dry_run: false }
GET  /tasks/status             → current running task (scrape|apply|idle) + progress

POST /resume/upload            → multipart DOCX upload
GET  /resume/parsed            → ResumeData JSON (merged with overrides)
PATCH /resume/fields           → save field overrides

WS   /ws/log                   → real-time log stream (newline-delimited JSON)
```

### Task Concurrency

Scrape and apply run as FastAPI `BackgroundTask`s (one at a time). The `/tasks/status` endpoint returns the active task type and a progress counter so the UI can show a spinner / progress bar. Starting a new task while one is running returns `409 Conflict`.

---

## Dependency Management

### Python (`uv`)

```bash
uv init
uv add anthropic playwright python-docx pydantic-settings structlog \
       aiosqlite fake-useragent tenacity fastapi uvicorn[standard] python-multipart
uv lock        # commit uv.lock
uv sync --frozen
```

### Frontend (`npm`)

```bash
cd ui
npm create vite@latest . -- --template react-ts
npm install @shadcn/ui tailwindcss @tanstack/react-table
npm run build
```

`pyproject.toml` pins a minimum Python version and declares all deps. `uv.lock` pins exact transitive versions. Together they guarantee identical environments across machines and CI.

---

## Reproducibility Checklist

A new machine needs only:

1. `git clone <repo>`
2. `cp .env.example .env` and fill in credentials
3. `docker compose up --build`
4. Open `http://localhost:8080`, upload your resume DOCX in the Resume tab

No Python version management, no `pip install`, no `playwright install`, no Node setup — everything is in the Docker build.

Resume DOCX is uploaded through the UI and stored in the `data/` volume — no manual file placement required.

---

## Implementation Order

Build in this sequence so each layer is testable before the next depends on it:

1. **Config + models** — `Config`, `JobListing`, `ResumeData` Pydantic models
2. **Queue/store** — SQLite schema, CRUD operations, `aiosqlite`
3. **Resume parser** — DOCX → `ResumeData`, override file merge
4. **AI client** — Anthropic SDK wrapper, all four decision types
5. **Scrapers** — LinkedIn first (most used), then Indeed, Dice, Monster
6. **Appliers** — LinkedIn Easy Apply, Workday, generic fallback
7. **FastAPI backend** — all routes, background task runner, WebSocket log stream
8. **React frontend** — Jobs table, Scrape panel, Apply panel, Resume panel
9. **Docker** — two-stage build, docker-compose, end-to-end smoke test

---

## Out of Scope (v2)

- Notifications (email/Slack) on application sent
- Multi-user / SaaS
- Answer memory (reusing past AI answers for identical questions)
- Scheduled/automated runs (cron inside container)

These are natural v3 additions once the core pipeline is solid.
