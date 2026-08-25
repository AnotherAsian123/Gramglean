<p align="center">
  <img src="icon.png" alt="Gramglean" width="128" height="128"/>
</p>

# Gramglean

Paste Instagram links, glean every image. **Gramglean** is a self-hosted
Instagram downloader that runs as a single Docker container on Unraid (or
anywhere Docker runs). Paste post/reel links to build a queue, manage it, and
hit **Download** when you're ready — the full-resolution media is archived
into a local folder, with a sleek web UI and a built-in gallery.

> ⚠️ **Read before using.** Automated scraping violates Instagram's Terms of
> Service and can get the account whose cookies you use **temporarily locked
> or banned**. Use a throwaway/secondary account, keep the rate limits sane,
> and only download content you have a legitimate reason to back up. You
> accept the risk.

---

## Features

- 🔗 **Link in, images out** — paste any number of post/reel links, one per line.
- 📋 **Manual queue** — links collect in a queue you can review, prune or clear;
  nothing downloads until you press Download.
- 🎠 **Complete carousels, guaranteed.** Instagram's web player only keeps ~3
  carousel slides in the DOM at a time, so HTML scrapers silently miss most of
  a large post. Gramglean never reads the rendered page: it pulls the post's
  full media manifest (the same data Instagram's own client uses), so a
  16-image carousel yields 16 images. Every time.
- 📸 **Full resolution** — the largest rendition Instagram serves, with
  width/height metadata when available.
- 🎬 **Videos too** — reels and carousel videos at the highest bitrate.
- 🍪 **Works without login** for public posts; upload one or more
  `cookies.txt` files for private/login-gated posts. Multiple cookies rotate
  (least-recently-used first) and fall back to anonymous fetching.
- ♻️ **Incremental** — re-submitting a link skips everything already archived.
- 🔁 **Retries with backoff** on failed downloads, plus a configurable thread
  pool and randomized rate limiting between post fetches.
- 📝 **Dual error reporting** — a friendly one-line summary in the UI, and the
  full detail (traceback, URL, HTTP status) in
  `/config/logs/failed_downloads.log`. Old per-job logs are pruned
  automatically after `LOG_RETENTION_DAYS`.
- 🔐 **Optional at-rest cookie encryption** (AES-256-GCM); decrypted cookies
  never touch disk.
- 🗂 **Metadata preserved** — JSON sidecar per file, caption, and the original
  post date as the file's modification time.
- 🖼 **Built-in gallery** with lightbox, keyboard navigation, and seekable
  video playback.

---

## Quick start

### Unraid

1. **Docker** tab → **Add Container** → paste this template's raw URL into the
   *Template* field (or copy [`unraid-template.xml`](unraid-template.xml) into
   `/boot/config/plugins/dockerMan/templates-user/`).
2. Set the **Config** path (e.g. `/mnt/user/appdata/gramglean`) and
   **Downloads** path (e.g. `/mnt/user/media/instagram`).
3. Apply, open the WebUI, paste links. For private posts, first go to
   **Settings → upload your cookies.txt**.

### docker-compose

```bash
git clone https://github.com/AnotherAsian123/Gramglean.git
cd Gramglean
docker compose up -d --build
# open http://localhost:8080
```

---

## How it gets every carousel image

For a post like `instagram.com/p/DcZ7gGEkiM8` (16 images), the browser DOM
only ever holds three `<li>` slides — the carousel is virtualized, and slides
are recycled as you click through. Scraping rendered HTML therefore misses
most of the post. Gramglean instead uses the two places where the complete
manifest lives:

1. **Anonymous:** the post page embeds a JSON payload
   (`<script type="application/json">`) whose media object contains the full
   `carousel_media` array with CDN URLs for every item — but Instagram only
   server-renders it when the request carries real browser navigation headers,
   which Gramglean sends.
2. **Authenticated** (cookies uploaded): the private web API
   `/api/v1/media/{pk}/info/` — the post's numeric `pk` is decoded offline
   from the shortcode (base64url), so no HTML round-trip is needed at all.

Both paths are normalized to the same structure; the highest-resolution
rendition of each item is selected and downloaded in parallel by an
`httpx` thread pool with retry + backoff.

---

## Getting your `cookies.txt` (optional, for private posts)

1. Log in to Instagram in your browser (use a **throwaway account**).
2. Install a "Get cookies.txt" browser extension.
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
| `DOWNLOAD_THREADS` | `4` | Parallel download workers. Also adjustable live in Settings. |
| `MAX_CONCURRENT_JOBS` | `1` | How many jobs run at once. Keep at `1`. |
| `RATE_LIMIT_MIN` / `RATE_LIMIT_MAX` | `2.0` / `5.0` | Randomized delay (s) between post fetches. Adjustable in Settings. |
| `LOG_RETENTION_DAYS` | `30` | Per-job logs older than this are deleted at startup. |
| `COOKIE_ENCRYPTION_KEY` | _(unset)_ | If set, cookie files are encrypted at rest with AES-256-GCM. |
| `LOG_LEVEL` | `INFO` | `INFO` or `DEBUG`. |

### Encrypting cookies at rest

Cookie files contain your Instagram `sessionid` (account-takeover material).
By default they're stored with `0600` permissions only. Set
`COOKIE_ENCRYPTION_KEY` to encrypt them at rest. Because the key lives in the
container's environment — **not** in the `/config` appdata share — a leaked or
backed-up appdata folder alone cannot decrypt them.

Generate a key:
```bash
python -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Passphrases (anything that isn't a 32-byte base64 key) are stretched with
scrypt. If you change or remove the key later, previously-encrypted cookies
can no longer be decrypted and will be flagged invalid — just re-upload them.

---

## Where things go

```
/config
  gramglean.db           SQLite (jobs, links, media index, settings)
  cookies/               uploaded cookie files (never overwritten)
  logs/
    gramglean.log        application log (rotating)
    failed_downloads.log full detail for every failed resource (rotating)
    job-<id>.log         per-job activity (pruned after LOG_RETENTION_DAYS)
    job-<id>.errors.log  per-job failures (pruned after LOG_RETENTION_DAYS)

/downloads
  <username>/
    20260824_<shortcode>.jpg          first carousel item
    20260824_<shortcode>_01.jpg       second item, and so on
    20260824_<shortcode>.jpg.json     metadata sidecar
```

Each file's modification time is set to the original Instagram post date.

---

## Development

Backend (FastAPI):
```bash
cd backend
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
CONFIG_DIR=./data/config DOWNLOAD_DIR=./data/downloads DEV_CORS=1 \
  uvicorn app.main:app --reload --port 8123
```

Frontend (Vite dev server, proxies the API to `:8123`):
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

---

## Upgrading from UnRaiders-of-the-lost-Sta

Gramglean is a ground-up rewrite (v2) centred on links instead of account
archiving. It uses a fresh database (`gramglean.db`) and does not migrate the
old `app.db`, and passphrase-derived encryption keys use a new KDF — re-upload
your cookie files. Downloaded files from v1 are untouched.

🤖 Built with [Claude Code](https://claude.com/claude-code)
