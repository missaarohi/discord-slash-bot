# Discord Slash-Command Bot

A small web app + Discord bot: admins connect a server from a dashboard,
users run `/status` and `/report <text>` in Discord, the app records and
reacts to each command, replies in Discord, and mirrors a notification to
a second channel (Slack or another Discord channel).

Built with **Django** (no separate always-on bot process needed - Discord
sends interactions as an HTTP POST to one endpoint).

## Status

Built, deployed, and manually tested end to end against a real Discord test
server: both slash commands, the mirror webhook, the "Mark Resolved" button,
the dashboard's live log and per-command config, and the login/logout flow
have all been exercised and verified working, not just written and assumed
correct.

## How it works

1. Discord sends every slash command as a signed HTTP POST to `/interactions`.
2. We verify the Ed25519 signature (`X-Signature-Ed25519` / `X-Signature-Timestamp`)
   before touching the body at all.
3. We answer within Discord's ~3 second window with a **deferred** response,
   then do the real work (apply the configured rule, call Discord's API to
   edit the reply, mirror to Slack/Discord) in a background thread.
4. Every interaction is logged to the database with its `interaction_id` as a
   unique key, so a redelivered/duplicate interaction never gets acted on twice.
5. An admin dashboard (behind Django login) shows the live log and lets you
   turn commands on/off, set a flag keyword, and edit the reply template -
   no redeploy needed.

## Project layout

- `discordbot/` - Django project settings/urls
- `bot/` - the app: models, the `/interactions` endpoint, dashboard views, templates
- `scripts/register_commands.py` - one-off script to register `/status` and `/report` with Discord

## Run it locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: at minimum set SECRET_KEY and DISCORD_PUBLIC_KEY.
# Leave DATABASE_URL blank to use a local sqlite file.

python manage.py migrate
python manage.py createsuperuser   # this becomes your admin dashboard login
python manage.py runserver
```

The dashboard is at `http://127.0.0.1:8000/`. Log in with the superuser you
just created.

Discord can't reach `localhost`, so to test the `/interactions` endpoint
locally you need to expose it publicly first - e.g. with `ngrok http 8000`,
or VS Code's built-in port forwarding (Ports panel -> Forward a Port ->
set visibility to Public). Whichever you use, set the Interactions Endpoint
URL in the Discord Developer Portal to `https://<your-public-url>/interactions`.
Discord immediately sends a PING - if the tunnel and `DISCORD_PUBLIC_KEY` are
correct, it saves right away.

## Environment variables

See `.env.example` for the full list. The important ones:

| Variable | What it's for |
|---|---|
| `SECRET_KEY` | Django secret key |
| `ALLOWED_HOSTS` | Comma-separated hostnames Django will accept requests for (needs your public URL's domain, no `https://`) |
| `CSRF_TRUSTED_ORIGINS` | Same idea, but the full origin with `https://` |
| `DATABASE_URL` | Postgres connection string (Neon/Supabase). Blank = local sqlite |
| `DISCORD_PUBLIC_KEY` | From your app's Developer Portal page - used to verify request signatures |
| `DISCORD_BOT_TOKEN` | Used server-side to edit replies / send follow-ups |
| `DISCORD_APPLICATION_ID` | Your application's ID |
| `GROQ_API_KEY` | Optional - only needed if you turn on the AI-summarize toggle in the dashboard |

None of these are ever committed, logged, or sent to the browser. The bot
token and public key live only in the hosting provider's environment
variable settings, and `.env` is git-ignored.

## Setting up the Discord app (one-time)

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**.
2. Under **Bot**, create a bot, copy the token into `DISCORD_BOT_TOKEN`.
3. Under **General Information**, copy the **Public Key** into `DISCORD_PUBLIC_KEY`
   and the **Application ID** into `DISCORD_APPLICATION_ID`.
4. Under **OAuth2 → URL Generator**, check `bot` and `applications.commands`,
   pick permissions (`Send Messages`, `Use Slash Commands`), open the
   generated URL to invite the bot to your test server.
5. Run `python scripts/register_commands.py` to register `/status` and `/report`.
6. Once your server is reachable at a public URL, set **Interactions
   Endpoint URL** (under General Information) to `https://<your-domain>/interactions`.

## Deployment

Deployed for free on **Render** (Web Service, free tier, no card):

1. Push this repo to GitHub.
2. On Render: **New → Web Service**, connect the repo.
3. Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
4. Start command: `gunicorn discordbot.wsgi`
5. Add all the env vars from `.env.example` (with real values) in Render's
   dashboard - set `DEBUG=False` and `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`
   to your Render URL.
6. Provision a free Postgres database on [Neon](https://neon.tech) or
   [Supabase](https://supabase.com), paste its connection string into
   `DATABASE_URL`.
7. After the first deploy, run `python scripts/register_commands.py` once
   (locally, pointed at the same bot token) and set the Interactions
   Endpoint URL in the Developer Portal to your Render URL + `/interactions`.

Render/Railway/Fly all work the same way for a Django + gunicorn app; swap
the build/start commands accordingly if you use a different host.

## Mirroring to a second channel

In the dashboard's "Connect a server" form, paste either:
- a **Slack Incoming Webhook URL** (Slack → App Directory → Incoming Webhooks), or
- a **Discord webhook URL** for a different channel (Channel Settings → Integrations → Webhooks).

Both are free, paste-a-URL, no card required.

## What's implemented vs. what's a stretch goal

**Core (done and tested):**
- Signed `/interactions` endpoint, PING/PONG, `/status` and `/report <text>`
- Deferred ack + background processing + edit-in-place reply
- Dedup on `interaction_id`
- Mirror to Slack or a second Discord channel
- Dashboard behind login: live command log + per-command config (enable/disable,
  flag keyword, reply template)
- Multi-server support, isolated per admin user

**Stretch goals attempted (done and tested):**
- A button ("Mark Resolved") on `/report` replies - a second, verified
  interaction type (`MESSAGE_COMPONENT`)
- Structured logging + an `error_message`/`status` field per interaction so
  failures are actually visible, not silent

**Stretch goals attempted (built, not exercised live):**
- Optional AI summarize toggle per server (Groq, free tier) - additive, the
  rest of the app works the same with it off

**Not implemented** (see `AI_NOTES.md` for what's next):
- Modal form for `/report` (currently a plain string option instead - simpler
  and functionally equivalent for this scope)
- A real task queue (Celery/RQ) instead of a plain background thread for the
  deferred work - fine at this scale, not what I'd ship at real volume

## Testing it

1. Log in to the dashboard, connect your test server (guild ID + a Slack or
   Discord webhook URL for the mirror channel).
2. In your Discord server, run `/status` - you should get a reply within a second
   or two, and a new row in the dashboard's log.
3. Run `/report some test text` - you should see the reply, a "Mark Resolved"
   button, a mirrored message in the second channel, and a new log row.
4. Click "Mark Resolved" - the log row updates.
5. Toggle a command off, or add a flag keyword, in the config page and try it
   again in Discord - the reply reflects the new config immediately.