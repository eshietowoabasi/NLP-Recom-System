# Running NLP-RS on your own computer (demo)

This runs the complete system (web app, API, background worker, database) on
your computer with Docker Desktop. Use it for demos and supervisor reviews. It
isn't secured for use on a network; for a real server see
[DEPLOYMENT.md](DEPLOYMENT.md).

## 1. Install Docker Desktop (once)

1. Download Docker Desktop from https://www.docker.com/products/docker-desktop/
   (Windows, macOS Intel or Apple Silicon) and install it.
   - On Windows, accept the WSL 2 option if it's offered, and restart when asked.
2. Start Docker Desktop and wait until it says **Engine running**.
3. Open **Settings → Resources** and give Docker at least **6 GB of memory**
   (8 GB is better) and **4 CPUs**, then click **Apply & restart**. The NLP
   worker needs about 3 GB.

You'll also need **Git** (https://git-scm.com/downloads) and about **10 GB of
free disk space**.

## 2. Get the code

Open a terminal: **PowerShell** on Windows, **Terminal** on macOS.

```bash
git clone https://github.com/eshietowoabasi/NLP-Recom-System.git
cd NLP-Recom-System
```

## 3. Build and start (the first time takes 10–20 minutes)

```bash
docker compose up -d --build
```

The first build downloads about 3 GB: Python, PyTorch (CPU), spaCy and the
SBERT model. Later starts take seconds. When it finishes, check that all six
services are running:

```bash
docker compose ps
```

You should see `postgres`, `redis`, `backend`, `worker`, `scheduler` and
`frontend`, each with status `running` or `healthy`.

## 4. Create the database tables and the first Admin (once)

```bash
docker compose exec backend flask db upgrade
docker compose exec backend flask create-user --role Admin
```

The second command asks for a username, email and password (at least 8
characters, typed twice).

## 5. Open the app

Go to **http://localhost:8080** and sign in with the Admin account.

Then, in this order:

1. **Admin → Core curriculum:** upload the **NUC CCMAS core curriculum** (PDF,
   DOCX, TXT, or a CSV course list with code, title and description columns).
   Only Admins can do this, and analyses need it for overlap detection. From
   the command line instead:
   `docker compose exec backend flask seed-core /data/raw/ccmas.csv` (copy the
   file into the container first with `docker compose cp`).
2. **Admin → NLP defaults** (optional): change the default overlap threshold,
   weights, number of recommendations or topic count for new sessions.
3. **Admin → Users:** create a *Curriculum Planner* account (create two if you
   want to show that planners can read each other's sessions but not change
   them).
4. Sign out, sign in as the planner, and drag source documents onto the
   **Documents** page: job adverts, policy documents and so on, as PDF, DOCX,
   TXT or CSV, up to 20 MB each.
5. **Sessions:** create a session, tick the documents and click **Run
   analysis**. The page shows each stage and opens the recommendations when the
   run finishes. 20 documents take about a minute; the very first run after a
   start takes about 30 seconds longer while the models load.
6. Review the recommendations (each card shows its score breakdown and a
   Clear/Flagged overlap badge), accept or reject some (Undo reverses a
   decision), map one to a course, and download the PDF report.

## Everyday commands

| What | Command |
|---|---|
| Stop everything (data is kept) | `docker compose stop` |
| Start again | `docker compose start` |
| See what the worker is doing | `docker compose logs -f worker` |
| Update after new code is merged | `git pull` then `docker compose up -d --build` then `docker compose exec backend flask db upgrade` |
| Delete everything, including data | `docker compose down -v` |

## If something goes wrong

| Symptom | Fix |
|---|---|
| `port is already allocated` for 8080 | Another program uses port 8080. In `docker-compose.yml`, change `"8080:80"` to `"8081:80"` and open http://localhost:8081 instead. |
| The page loads, but sign-in says the server can't be reached | The backend isn't ready yet: wait 20 seconds, or check `docker compose logs backend`. |
| An error mentioning a missing table (`relation … does not exist`) | Step 4 (`flask db upgrade`) hasn't been run. |
| An analysis stays on "Processing" or fails with "worker stopped responding" | Usually Docker has too little memory. Raise it in Settings → Resources, run `docker compose restart worker`, then click **Retry analysis**. |
| "No NUC Core Reference document" | Sign in as Admin and upload the CCMAS document with that category. |
| The build fails while downloading | Check your internet connection and run `docker compose up -d --build` again; finished steps are cached. |
