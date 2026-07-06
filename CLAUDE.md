# Instructions given to Claude while building this

Per the assignment's request for AI context/instruction files "exactly as
used" - this is the actual working brief I gave Claude, kept here for
transparency about how the collaboration worked.

## Direction I gave

- I chose Django/Python as the stack (over other stacks that were offered),
  with Postgres for production (Neon/Supabase) and sqlite for local dev.
- Build the assignment as described: a web app + Discord bot where an admin
  logs in, connects a Discord server, and slash commands (`/status`,
  `/report <text>`) get recorded, acted on, replied to in Discord, and
  mirrored to a second channel.
- Cover the specific technical requirements the brief calls out: verify
  Discord's Ed25519 request signature, answer PING with PONG, respond within
  the ~3 second window using a deferred ack + background processing, dedup on
  `interaction_id`, and never put secrets in the repo or client-side code.
- Attempt a couple of stretch goals on top of the core: a button interaction
  on `/report` replies, and an optional AI-summarize toggle - but keep the
  core solid rather than spreading thin across every stretch goal.
- Write the README, AI_NOTES.md, and this file to match what the assignment
  asks for.

## Working style I asked for

- Prefer clear, readable code over cleverness - this needs to run unattended,
  not just work once in a demo.
- Comment on *why*, not *what*, especially around the Discord-specific
  details that are easy to get subtly wrong (the order of signature
  verification vs. JSON parsing, the interaction-type vs. response-type
  number overlap, the deferred-ack pattern).
- Be explicit in the README/AI_NOTES about anything not fully tested or not
  implemented, rather than implying the project is more finished than it is.

## What happened after the initial generation

Everything past this point - installing dependencies, setting up the Discord
application and bot, connecting it to a real test server, configuring the
mirror webhook, running migrations, creating the admin login, exposing the
local server publicly so Discord could reach it, registering the commands,
and testing every command and the dashboard end to end - was integration work
I did myself, outside of what Claude generated. I also caught and reported
two real bugs in the login/logout flow through my own manual testing (see
AI_NOTES.md for details), which were then fixed based on the specific
behavior I described.