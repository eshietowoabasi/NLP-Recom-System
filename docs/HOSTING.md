# Hosting the demo on Hugging Face

This puts NLP-RS on the internet at an address like
`https://yourname-nlp-rs.hf.space`, free, with no server to manage. A Hugging Face
**Docker Space** runs the whole system in one container: PostgreSQL, Redis, the API,
the NLP worker, the scheduler and the web app (`deploy/huggingface/`). The free
"CPU basic" hardware has 16 GB of memory, enough for SBERT, spaCy and BERTopic.

**Limits of the free Space**

- **Data is not kept.** Uploads, sessions and accounts live inside the container and
  are wiped whenever the Space restarts, rebuilds (every deploy) or wakes from sleep.
  Keep your source documents and re-upload them after a restart. For lasting data,
  add *Persistent storage* in the Space settings (paid; the app uses `/data`) or use a
  server with `docs/DEPLOYMENT.md`.
- **It sleeps** after 48 hours without visitors. The next visit wakes it (a minute
  or two) with empty data.
- **Speed:** 2 CPU cores. An analysis of ~20 documents takes a few minutes.

## One-time setup (about 15 minutes)

1. **Create a Hugging Face account** at https://huggingface.co/join.
2. **Create an access token:** *Settings → Access Tokens → Create new token*, type
   **Write**. Copy it.
3. **Give GitHub the token and the Space name.** In the GitHub repository:
   *Settings → Secrets and variables → Actions*.
   - *Secrets* tab → **New repository secret**: name `HF_TOKEN`, value the token.
   - *Variables* tab → **New repository variable**: name `HF_SPACE`, value
     `<your-hf-username>/nlp-rs`.
4. **Deploy:** *Actions → Deploy to Hugging Face → Run workflow* (it also runs
   automatically on every push to `main`). It creates the Space and uploads the app.
5. **Set the Space's secrets** (the Space now exists): on Hugging Face open the Space
   → *Settings → Variables and secrets → New secret*:
   - `ADMIN_PASSWORD`: the Admin password you want (at least 8 characters).
   - `ADMIN_USERNAME` (optional, default `admin`) and `ADMIN_EMAIL` (optional).
   - `SECRET_KEY`: 48+ random characters, e.g. from
     `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Without it, a
     new key is generated at each start (people just sign in again).

   Saving a secret restarts the Space.
6. **Wait for the build** (the first one takes 10–15 minutes; watch the *Logs*
   tab). When the status shows **Running**, open
   **`https://<your-hf-username>-nlp-rs.hf.space`**.

   Use that direct address. Inside the Hugging Face page (`huggingface.co/spaces/…`)
   the app is shown in a frame where the browser won't send the sign-in cookie.

## Using it

Sign in as the Admin, then as in `docs/LOCAL_DEMO.md` step 5: **Admin → Core
curriculum** to upload the CCMAS, **Admin → Users** to add planners, then upload
source documents and run an analysis.

If you didn't set `ADMIN_PASSWORD`, a temporary Admin password is printed in the
Space's *Logs* tab at each start (only the Space owner can see the logs).

The Space is public by default: anyone with the address sees the sign-in page, but
nothing else without an account. Making the Space **private** limits even the
sign-in page to Hugging Face users you add to it.

## Updating

Merge to `main`; the workflow redeploys and the Space rebuilds (data resets).

## If something goes wrong

| Symptom | Fix |
|---|---|
| The workflow is skipped | The `HF_SPACE` variable isn't set (step 3). |
| The workflow fails with "Set the HF_TOKEN secret…" | Add the `HF_TOKEN` secret (step 3); the token must be type **Write**. |
| The Space shows *Build error* | Open *Logs → Build* and send me the last lines. |
| The Space shows *Runtime error* | Open *Logs → Container* and send me the last lines. |
| Sign-in doesn't stick | You're on `huggingface.co/spaces/…`; open the `….hf.space` address instead. |
| Everything is empty | The Space restarted; data isn't kept on the free tier. |
