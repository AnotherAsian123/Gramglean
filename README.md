# UnRaiders of the lost Sta

A self-hosted **Instagram archiver** that runs as a single Docker container on
Unraid (or anywhere Docker runs). Type a username, hit **Scrape**, and it pulls
full-resolution **posts, carousels, reels and stories** into a local folder —
with an Instagram-inspired web UI.

> ⚠️ **Read before using.** Automated scraping violates Instagram's Terms of
> Service and can get the account whose cookies you use **temporarily locked or
> banned**. Use a throwaway/secondary account, keep the rate limits sane, and
> only archive content you have a legitimate reason to back up. You accept the
> risk.

---

## Features

- 📸 **Full-resolution** images and videos — the largest rendition Instagram serves.
- 🎠 **Carousels** — every photo/video in a multi-image post (no browser needed;
  it reads Instagram's JSON API directly).
- 🎬 **Reels** at the highest available bitrate.
- ⏳ **Stories** (toggle) — captured before they expire.
- ♻️ **Incremental sync** — re-running an account only fetches *new* posts and
  stops early once it reaches already-archived history.
- 🍪 **Multi-cookie rotation** — upload several `cookies.txt` files; the scraper
  cycles through them to spread load and dodge rate limits. Uploads never
  overwrite existing cookies.
- 🧵 **Parallel downloads** — a configurable thread pool (`DOWNLOAD_THREADS`).
- 🐢 **Configurable, randomized rate limiting** with a safety-first default.
- 📝 **Detailed per-resource error logs** — one line per failed picture/reel/story
  explaining exactly what went wrong (HTTP status, exception, URL), kept on disk
  for review.
- 🗂 **Metadata preserved** — captions, dates and a JSON sidecar per file, plus the
  original post date written as the file's modification time.
- 🖼 **Built-in gallery** with a swipeable lightbox and inline reel playback.

---

## Quick start

### Unraid

1. **Docker** tab → **Add Container** → paste this template's raw URL into the
   *Template* field (or copy [`unraid-template.xml`](unraid-template.xml) into
   `/boot/config/plugins/dockerMan/templates-user/`).
2. Set the **Config** path (e.g. `/mnt/user/appdata/unraiders`) and **Downloads**
   path (e.g. `/mnt/user/media/instagram`).
3. Apply, then open the WebUI and go to **Settings → upload your cookies.txt**.

### docker-compose

```bash
git clone https://github.com/OWNER/UnRaiders-of-the-lost-Sta.git
cd UnRaiders-of-the-lost-Sta
docker compose up -d --build
# open http://localhost:8080
```

---

## Getting your `cookies.txt`

Reliable archiving needs a logged-in session.

1. Log in to Instagram in your browser (use a **throwaway account**).
2. Install a "cookies.txt" / "Get cookies.txt" browser extension.
3. Export cookies for `instagram.com` (Netscape format).
4. In the app: **Settings → Upload cookies.txt**. Add more than one (from
   different accounts) to enable rotation.

---

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `PUID` / `PGID` | `99` / `100` | User/group for file ownership (Unraid `nobody:users`). |
| `UMASK` | `022` | File-creation mask. |
| `TZ` | `Etc/UTC` | Timezone for timestamps. |
| `PORT` | `8080` | Web UI port. |
| `DOWNLOAD_THREADS` | `4` | Parallel download workers. Higher = faster, but more requests = higher ban risk. Also adjustable live in Settings. |
| `MAX_CONCURRENT_JOBS` | `1` | How many account scrapes run at once. Keep at `1`. |
| `RATE_LIMIT_MIN` / `RATE_LIMIT_MAX` | `2.0` / `5.0` | Randomized delay (s) between API page requests. Adjustable in Settings. |
| `COOKIE_ENCRYPTION_KEY` | _(unset)_ | If set, cookie files are encrypted at rest with AES-256-GCM. Unset = plaintext (file-perms only). See below. |
| `LOG_LEVEL` | `INFO` | `INFO` or `DEBUG`. |

### Encrypting cookies at rest

Cookie files contain your Instagram `sessionid` (account-takeover material). By
default they're stored with `0600` permissions only. Set `COOKIE_ENCRYPTION_KEY`
to encrypt them at rest with **AES-256-GCM**. Because the key lives in the
container's environment — **not** in the `/config` appdata share — a leaked or
backed-up appdata folder alone cannot decrypt them.

Generate a key:
```bash
python -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```
Notes: encryption protects against backup/snapshot/share leaks, **not** full root
compromise of the host (whoever can read the running container can read the key).
If you change or remove the key later, previously-encrypted cookies can no longer
be decrypted and will be flagged invalid — just re-upload them.

### Why threads, not processes?
Downloading is **network/IO-bound**: the workers spend their time waiting on the
network, during which Python releases the GIL, so threads run concurrently with
none of the memory-duplication or data-serialization overhead that separate
processes would add. We do no CPU-heavy work on our side (no transcoding), so
multiprocessing would only be slower and heavier here.

---

## Where things go

```
/config
  app.db                 SQLite (accounts, jobs, media index, settings)
  cookies/               your uploaded cookie files (cycled, never overwritten)
  logs/
    app.log              general application log
    job-<id>.log         per-job activity
    job-<id>.errors.log  one line per FAILED resource for that job
    errors.log           every failure across all jobs

/downloads
  <username>/
    post/      carousel/      reel/      story/
      20240131_<shortcode>.jpg
      20240131_<shortcode>.jpg.json   (metadata sidecar)
```

Each file's modification time is set to the original Instagram post date.

---

## Development

Backend (FastAPI):
```bash
cd backend
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
CONFIG_DIR=./data/config DOWNLOAD_DIR=./data/downloads \
  uvicorn app.main:app --reload --port 8080
```

Frontend (Vite dev server, proxies the API to `:8080`):
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

---

## How it works

`instaloader` (Python API) **enumerates** the account — resolving carousels,
reels and stories to their full-resolution URLs plus metadata — while our own
`ThreadPoolExecutor` + `httpx` **downloads** every new resource in parallel. That
split is what gives us per-resource failure logging, our own incremental archive
(the `media` table), exact timestamp/metadata control, and cookie rotation on
rate-limit. FastAPI serves the JSON API + a WebSocket for live progress and hosts
the built React/Tailwind/Framer-Motion SPA.

See [`plan.md`](plan.md) for the full design rationale and roadmap.

---

## Roadmap (not yet built)

Scheduled auto-sync, completion notifications (ntfy/Discord/webhook), proxy
support, storage dashboard, highlights, and optional UI auth. PRs welcome.

🤖 Built with [Claude Code](https://claude.com/claude-code)
