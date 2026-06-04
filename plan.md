# UnRaiders of the lost Sta — Project Plan

An self-hosted web app that archives images and reels from a specified Instagram
account, in the highest resolution Instagram serves, running as a single Docker
container on an Unraid server.

> **Status:** Planning. Nothing has been built yet. This document is for your
> review and sign-off before any code is written or any GitHub repo is created.

---

## 1. Read this first — three reality checks

Per CLAUDE.md §1 ("don't assume, surface tradeoffs"), three of your requirements
need clarification before we lock the design. None are blockers; they change
*how* we build, not *whether* we can.

### 1a. "Handle the JavaScript that Instagram uses to scroll through multiple photos in a single post"

This is the most important correction. You do **not** need a browser/JavaScript
engine to get every photo in a carousel post.

When you load an Instagram post, the page fetches a JSON payload (Instagram's
GraphQL / private REST API) that already contains **every** child image and video
of a carousel, each with its full set of resolution candidates. The on-page
"swipe through photos" interaction is just the front-end rendering data it already
has.

Mature scrapers (`gallery-dl`, `instaloader`) talk to that JSON API directly and
pull **all** carousel children — and reels, and stories — in one request, at
original resolution. This is:

- **Faster** (one API call vs. driving a headless browser).
- **Higher quality** (we read the original-resolution URL straight from the API).
- **More reliable** (no brittle DOM selectors that break on every IG redesign).
- **Less detectable** (a headless Chromium fingerprint is a classic bot signal).

**Recommendation:** use an API-based extractor (`gallery-dl`), **not** Selenium/
Playwright. We keep a headless-browser fallback in our back pocket only if Meta
ever kills the JSON endpoints, but we don't build it on day one. This removes a
huge amount of complexity, RAM usage, and fragility from the container.

### 1b. "Highest possible definition"

We will always request the **largest candidate Instagram exposes** (the original
upload). Caveats to set expectations:

- **Photos:** typically the original upload, up to ~1080px on the long edge for
  older posts and full original for newer ones. Instagram itself re-compresses on
  upload, so "original" = "what IG stored," not the photographer's RAW.
- **Reels / videos:** highest available rendition, usually **1080p** (Instagram
  rarely stores higher). We pick the top bitrate/resolution variant from the
  manifest. There is no 4K hiding behind a flag — IG simply doesn't serve it.

So "highest possible" = "the best Instagram will give us," which is exactly what
`gallery-dl` does by default.

### 1c. Authentication, rate limits, and account-ban risk (the real constraint)

As of 2026, **anonymous** Instagram scraping is throttled to roughly **1–2
requests / 30 seconds** and trips security checks fast. To archive a whole
account reliably you must be **logged in via cookies**.

Implications baked into this plan:

- The app needs a place to import an Instagram **session cookie** (Netscape
  `cookies.txt`, exported from a logged-in browser). We'll build a clean upload
  flow for this.
- **Strongly recommend a throwaway/secondary IG account** for scraping. There is
  a real risk of temporary locks or bans on whatever account's cookies you use.
  This is inherent to scraping Instagram, not a flaw in our app.
- We will default to **conservative, randomized request delays** and a
  configurable rate limit, and surface ban/lock errors clearly in the UI.
- **Legal/ToS note:** automated scraping violates Instagram's Terms of Service.
  This tool is intended for **personal archival of accounts you own or have a
  legitimate reason to back up**. Use responsibly; you accept the risk to any
  account whose credentials you supply.

---

## 2. Recommended tech stack

| Layer | Choice | Why |
|---|---|---|
| **Scraper engine** | **`gallery-dl`** (Python) | Original-resolution downloads; native carousel/reel/story/highlight support via one `include` setting; cookie auth; built-in rate-limit controls; incremental "download archive"; actively maintained. |
| **Backend / API** | **FastAPI** (Python 3.12+) | Same language as the scraper (call it in-process or as subprocess), async, first-class WebSocket/SSE for live progress, tiny footprint. |
| **Job execution** | **In-process async worker + SQLite-backed queue** | Single container, no Redis. A bounded worker pool runs scrape jobs; state persists in SQLite so jobs survive restarts. (Redis + `arq`/Celery noted as an optional scale-up, deliberately *not* day one — CLAUDE.md §2.) |
| **Database** | **SQLite** | One file in `/config`. Perfect for a single-container self-hosted app; zero admin. |
| **Frontend** | **React + TypeScript + Vite** | Fast, modern, the de-facto standard; great component ecosystem. |
| **Styling** | **Tailwind CSS** + **shadcn/ui** | Rapidly build a polished, consistent Instagram-like theme; accessible primitives. |
| **Animation** | **Framer Motion** | Smooth, "sexy not jank" transitions, carousels, skeleton loaders. |
| **Real-time** | **WebSocket** (FastAPI) | Live per-post download progress, log streaming, job status. |
| **Container** | **Single multi-stage Docker image** | Build React → static assets served by FastAPI; one image, one port. Unraid-friendly entrypoint for PUID/PGID/UMASK/TZ. |

**Why one container, not docker-compose:** Unraid installs containers one at a
time via templates. A self-contained single image (no external Redis/Postgres) is
dramatically simpler to install, back up, and maintain — which is the whole point
of an Unraid appliance. We trade a little horizontal scalability we don't need.

### Alternatives considered (and rejected for day one)

- **instaloader** — excellent and Python-native, but `gallery-dl`'s unified
  `include: posts,reels,stories,highlights` config and original-res handling make
  it the cleaner engine. We can swap/add it later behind our job abstraction.
- **Playwright/Selenium** — only needed if the JSON API dies (see §1a). Heavy,
  fragile, detectable. Kept as a documented fallback, not built.
- **Celery + Redis** — overkill for one user archiving a handful of accounts.
- **Next.js** — SSR buys us nothing for a LAN-only tool; Vite SPA is lighter.

---

## 3. Scraper engine details (`gallery-dl`)

Generated config (`/config/gallery-dl.conf`), tuned for max quality + safety:

```jsonc
{
  "extractor": {
    "base-directory": "/downloads",
    "instagram": {
      "cookies": "/config/cookies.txt",
      "include": "posts,reels,highlights,stories",  // user-selectable per job
      "videos": true,
      "previews": false,
      "highlights": true,
      "api": "rest",
      "order-posts": "asc",
      "order-files": "asc",
      "sleep-request": [5.0, 9.0],   // randomized human-like delay
      "directory": ["{username}", "{typename}"],
      "filename": "{date:%Y%m%d}_{shortcode}_{num}.{extension}",
      "archive": "/config/archive.sqlite",  // incremental: skip already-downloaded
      "metadata": true,                      // write caption/date sidecars
      "write-metadata": true
    }
  },
  "downloader": {
    "retries": 4,
    "timeout": 30.0
  }
}
```

Key behaviors we get for free:
- **Carousels:** every child downloaded (`{num}` in filename), full res.
- **Reels:** highest-bitrate MP4.
- **Incremental sync:** the `archive` DB means re-running an account only fetches
  *new* posts — fast, polite, ban-friendly.
- **Metadata sidecars:** caption, timestamp, likes preserved as JSON.

We invoke `gallery-dl` as a **subprocess** and parse its `--write-info-json` /
progress output, OR import it as a Python library for finer-grained progress
events. (Subprocess first for simplicity; library mode is a later refinement.)

---

## 4. Architecture

```
┌────────────────────────── Docker container ──────────────────────────┐
│                                                                       │
│  Browser (LAN)                                                        │
│      │  HTTP + WebSocket                                              │
│      ▼                                                                │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ FastAPI app (uvicorn)                                          │    │
│  │  • Serves built React SPA (static)                            │    │
│  │  • REST API: accounts, jobs, media, settings                 │    │
│  │  • WebSocket: live job progress + log stream                  │    │
│  └───────────────┬───────────────────────────┬──────────────────┘    │
│                  │                             │                       │
│         ┌────────▼────────┐          ┌─────────▼─────────┐            │
│         │ SQLite (/config)│          │ Async job worker  │            │
│         │  jobs, accounts │◀────────▶│  (bounded pool)   │            │
│         │  media index    │          │  runs gallery-dl  │            │
│         └─────────────────┘          └─────────┬─────────┘            │
│                                                 │ subprocess           │
│                                       ┌─────────▼─────────┐            │
│                                       │   gallery-dl      │            │
│                                       │  + cookies.txt    │            │
│                                       └─────────┬─────────┘            │
│                                                 │ writes               │
│                                       ┌─────────▼─────────┐            │
│                                       │  /downloads       │ (Unraid    │
│                                       │  /{user}/{type}/  │  share)    │
│                                       └───────────────────┘            │
│  Volumes:  /config (db, cookies, conf)   /downloads (media)           │
│  Env:      PUID PGID UMASK TZ  PORT                                   │
└───────────────────────────────────────────────────────────────────────┘
```

**Data flow for one scrape:**
1. User enters an IG username + selects content types in the UI.
2. `POST /api/jobs` creates a job row (status `queued`) and notifies the worker.
3. Worker spawns `gallery-dl`, streams progress over WebSocket to the UI.
4. Each downloaded file is indexed into SQLite (path, type, shortcode, date).
5. Job → `completed`; the in-app gallery refreshes to show new media.

---

## 5. UI / UX design — "Instagram, but smoother"

Goal: instantly recognizable as Instagram-flavored, but cleaner, faster, and
more deliberate than the real app.

### Visual language
- **Signature gradient** (logo/accents/active states):
  `#405DE6 → #5851DB → #833AB4 → #C13584 → #E1306C → #FD1D1D`.
- **Light + dark themes**, dark as default (Instagram's modern look). Near-black
  `#000`/`#121212` surfaces, `#FAFAFA` light mode.
- **Typography:** "Instagram Sans" is proprietary and not redistributable, so we
  use a close, free stand-in — **Inter** (or system UI stack) — for a clean,
  modern feel without IP issues.
- **Layout cues borrowed from IG:** top nav bar, a left sidebar on desktop,
  rounded avatars with a gradient story-ring, a responsive 3-column media grid,
  bottom sheet/modals on mobile.
- **Iconography:** Lucide (outline icons matching IG's stroke style).

### What makes it "sexy, not jank"
- **Framer Motion** page/route transitions, springy modal opens, shared-element
  zoom from grid thumbnail → lightbox.
- **Skeleton shimmer** loaders instead of spinners.
- **Optimistic UI** + buttery WebSocket progress bars (per-file and per-job).
- **Lazy-loaded, virtualized media grid** so a 5,000-image archive scrolls at
  60fps.
- **A real lightbox** for carousels: swipe/keyboard nav through a post's children,
  with reel inline video playback.

### Core screens
1. **Dashboard** — add-account input (the hero), recent jobs, storage stats,
   quick links to archived accounts.
2. **Job view** — live log + progress, content-type toggles
   (Posts / Reels / Stories / Highlights), pause/cancel.
3. **Gallery browser** — per-account grid, filter by type, lightbox viewer,
   download-to-device, caption/metadata panel.
4. **Settings** — cookie import, rate-limit slider, default content types,
   theme, storage path info, scheduled-sync config.

---

## 6. Docker / Unraid deployment

### Image strategy
Multi-stage build:
1. **Stage 1 (node):** `npm ci && npm run build` → static React bundle.
2. **Stage 2 (python:3.12-slim):** install FastAPI, `gallery-dl`, `ffmpeg`
   (for reel muxing), copy the built SPA, run via uvicorn.

### Unraid-friendly runtime
- **Entrypoint** maps the container user to `PUID`/`PGID` (default `99`/`100`)
  and applies `UMASK` (default `022`) so files on the array are owned correctly —
  the LinuxServer.io convention Unraid users expect.
- **`TZ`** for correct timestamps.
- Single exposed **`PORT`** (default `8080`) for the web UI.
- Built-in **`HEALTHCHECK`** hitting `/api/health`.

### Volumes
| Container path | Purpose | Example host path |
|---|---|---|
| `/config` | SQLite db, `cookies.txt`, `gallery-dl.conf`, archive db | `/mnt/user/appdata/unraiders` |
| `/downloads` | All scraped media | `/mnt/user/media/instagram` |

### Deliverables for easy install
- A published image (GitHub Container Registry via GitHub Actions).
- An **Unraid Community-Apps template XML** so it installs with two clicks and
  pre-filled volume/env hints.
- `docker-compose.yml` for non-Unraid users.

---

## 7. Data model (SQLite)

- **account** — `id, username, added_at, last_synced_at, default_include`.
- **job** — `id, account_id, status, include_types, created_at, started_at,
  finished_at, stats_json, error`.
- **media** — `id, account_id, job_id, shortcode, type(image|video|carousel_child),
  file_path, width, height, taken_at, caption, is_reel`.
- **setting** — key/value (rate limit, theme, schedule, cookie present flag).

---

## 8. API surface (REST + WS)

```
GET    /api/health
GET    /api/accounts                 list tracked accounts
POST   /api/accounts                 add account
DELETE /api/accounts/{id}
POST   /api/jobs                     start a scrape  {username, include[]}
GET    /api/jobs        /{id}        list / detail
POST   /api/jobs/{id}/cancel
GET    /api/media?account=&type=     paged, for the gallery grid
GET    /api/media/{id}/file          stream/serve a file
POST   /api/settings/cookies         upload cookies.txt
GET/PUT /api/settings
WS     /ws/jobs/{id}                 live progress + log lines
```

---

## 9. Suggested improvements & missing features

Things you didn't ask for but that make this genuinely good. **Bold = recommend
for v1**; the rest are a backlog.

- **Incremental sync** (only new posts) — *free with `gallery-dl` archive db.* **(v1)**
- **In-app gallery viewer** — archiving is pointless if you can't browse it. **(v1)**
- **Cookie/session import flow + clear ban/lock error surfacing.** **(v1)**
- **Configurable, randomized rate limiting** with a safety-first default. **(v1)**
- **Metadata preservation** (captions, dates, original timestamps on files). **(v1)**
- **Scheduled auto-sync** (e.g. "re-check this account nightly") — Unraid users
  love set-and-forget. *(v2, high value)*
- **Multi-account watchlist** with per-account settings. *(v2)*
- **Completion notifications** via webhook / ntfy / Discord. *(v2)*
- **Storage dashboard** (space used per account, file counts). *(v2)*
- **Stories** as a toggle (ephemeral content archival, captured before expiry). **(v1)**
- **Highlights** toggle — `gallery-dl` supports it natively; deferred to backlog. *(backlog)*
- **Proxy support** for users who route scraping through a VPN/proxy. *(v2)*
- **Tag/favorite/notes** on saved media. *(backlog)*
- **Export** an account archive as a zip. *(backlog)*
- **Headless-browser fallback engine** if IG's JSON API changes. *(contingency)*

---

## 10. Security & safety

- **LAN-only by design.** No auth on the web UI in v1 (typical for Unraid apps
  behind the home network). *Optional* simple username/password gate as a v2
  setting if you ever expose it.
- **Cookie file** stored in `/config` with `600` perms; never logged, never sent
  anywhere except Instagram. UI shows only "cookies present/absent," never the
  value.
- **Input validation** on usernames (strict charset) to prevent command
  injection into the `gallery-dl` subprocess; we pass args as a list, never via a
  shell string.
- **No telemetry**, fully offline except for traffic to Instagram itself.

---

## 11. Build phases (each with a verification gate — CLAUDE.md §4)

1. **Repo scaffold + CI**
   → verify: `docker build` succeeds; container boots and `/api/health` returns ok.
2. **Scraper core (headless)** — wrap `gallery-dl`, cookie config, one account
   end-to-end from a CLI/test.
   → verify: an automated test downloads a small known public account's first
   post (carousel) at full res into `/downloads`.
3. **Backend API + SQLite + job worker** — jobs persist, run, and report status.
   → verify: `POST /api/jobs` runs a real scrape; job row transitions
   queued→running→completed; media rows indexed.
4. **WebSocket progress** — live updates.
   → verify: a test client receives progress events for a running job.
5. **Frontend shell + Instagram theme** — nav, dashboard, dark theme, gradient.
   → verify: SPA builds and is served by FastAPI; Lighthouse/visual check.
6. **Job UI + live progress** — start a scrape from the browser, watch it run.
   → verify: manual run of a real account from the UI start-to-finish.
7. **Gallery browser + lightbox** — browse/zoom/play archived media.
   → verify: archived carousel and a reel both display and play correctly.
8. **Unraid packaging** — entrypoint (PUID/PGID/UMASK/TZ), template XML,
   compose file, published image.
   → verify: container respects PUID/PGID on file ownership; template imports.
9. **v1 polish** — settings, rate-limit control, error states, docs/README.
   → verify: full README run-through on a clean install.

---

## 12. Proposed repository structure

```
UnRaiders-of-the-lost-Sta/
├── plan.md                  ← this file
├── README.md
├── Dockerfile               ← multi-stage
├── docker-compose.yml
├── unraid-template.xml
├── .github/workflows/       ← build + push image to GHCR
├── backend/
│   ├── app/
│   │   ├── main.py          ← FastAPI + static serving + WS
│   │   ├── api/             ← routers
│   │   ├── jobs/            ← worker + gallery-dl wrapper
│   │   ├── db/              ← SQLite models + migrations
│   │   └── core/            ← config, settings
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/      ← grid, lightbox, progress, nav
│   │   ├── pages/           ← dashboard, job, gallery, settings
│   │   ├── lib/             ← api client, ws hook
│   │   └── theme/           ← tailwind config, gradient tokens
│   ├── index.html
│   └── package.json
└── docs/
    └── screenshots/
```

---

## 13. Decisions (locked)

- **Content scope (v1):** **Posts (photos + carousels), Reels, and Stories.**
  Highlights deferred to backlog. (Stories require a logged-in cookie session and
  are captured before they expire.)
- **Scheduling:** **v2** — v1 ships manual/on-demand scrapes; nightly auto-sync
  comes later.
- **Account model:** **Watchlist of many accounts**, each saved with its own
  settings and re-syncable on demand.
- **GitHub repo:** **Private**, created under your account on approval.

### Still to confirm (not a blocker for building)

- **Auth:** Do you have an Instagram account — ideally a throwaway — whose cookies
  you'll import? The cookie-upload flow gets built regardless, but reliable
  scraping depends on you having a session to import. Recommend a secondary
  account given the lock/ban risk (§1c).

---

## 13b. Addendum — as built (v1)

The following were added/changed during implementation per your instructions:

**Variations implemented (from §9):** incremental sync, cookie import + multi-file
**rotation** (uploads never overwrite; the scraper cycles cookies on rate-limit),
configurable randomized rate limiting (env + live UI), metadata preservation
(captions, JSON sidecars, original post date as file mtime), and Stories as a
toggle.

**Added on request:**
- **Detailed per-resource error logs.** Every failed picture/reel/story is written
  as one line — timestamp, source, shortcode, child index, media type, HTTP
  status, exception, URL — to `/config/logs/job-<id>.errors.log` and a shared
  `/config/logs/errors.log`. Viewable in the job UI's *Failures* tab.
- **Parallel downloads via threads.** Judgment call: downloading is IO-bound, so a
  `ThreadPoolExecutor` (GIL released during network IO) is faster and lighter than
  multiprocessing, which only wins for CPU-bound work. Controlled by the
  **`DOWNLOAD_THREADS`** env var (and adjustable live in Settings).

**Engine deviation (gallery-dl → instaloader Python API).** The three custom
requirements above need programmatic control of each individual download.
gallery-dl is a black-box subprocess; bending it to per-resource logging + our own
thread pool + cookie rotation is fragile and untestable. So we use **instaloader's
Python API to enumerate** (carousels, reels, stories → full-res URLs + metadata)
and our **own httpx + thread-pool downloader**. Net: one Python dependency, full
control, and the incremental archive lives in our own SQLite `media` table.

**UI deviation (shadcn/ui → hand-rolled Tailwind).** shadcn requires a generator
step; hand-rolled Tailwind components (with the same Instagram theme, Framer Motion,
Lucide icons) are simpler, fully controllable, and avoid a build dependency.

**Verification done:** backend imports + DB init + all routers + the threaded job
worker were exercised end-to-end via a FastAPI `TestClient` smoke test (health,
settings round-trip, username validation, cookie-junk rejection, and a job running
to a graceful "no cookies" failure). The frontend is transpiled by Vite/esbuild in
the Docker build.

## 14. What happens on approval

1. Initialize git, create the GitHub repo **UnRaiders-of-the-lost-Sta**, first
   commit (this plan + scaffold).
2. Execute build phases 1→9 with the verification gate at each step.
3. Deliver a working single-container image + Unraid template + README.

*No GitHub repo or code will be created until you approve this plan.*
