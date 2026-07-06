# AI Notes

## Tools and models used, and how work was split

I used **Claude (Anthropic)** as my main AI collaborator for this project.
The split worked roughly like this:

- I gave the direction: which stack to use (I chose Django over other
  options I was offered), which stretch goals to attempt, and how I wanted
  the config/dashboard behavior to work.
- Claude generated the initial implementation from that brief - the Django
  project structure, models, the signed `/interactions` endpoint, the
  background-thread deferred-response handling, the dashboard views/templates,
  and the docs.
- From there, **I did all of the integration work myself**: setting up the
  Python virtual environment, installing dependencies, creating the Discord
  application/bot in the Developer Portal, inviting the bot to a test server,
  creating the mirror-channel webhook, running migrations, creating the admin
  account, forwarding the local port publicly so Discord could reach it, and
  registering the slash commands. None of that is automatic - it's the actual
  "wiring together several external services" the brief calls out as the heart
  of the exercise, and I did it end to end by hand, service by service.
- I also found and reported two real bugs through manual testing rather than
  by reading the code: after logging out, the dashboard would still show up
  in the browser back button instead of returning to the login page, and the
  logout link itself returned an empty page (a GET-vs-POST issue with
  Django's logout view). I described the exact behavior I was seeing in both
  cases, which is what let the fix get targeted correctly instead of guessing.
- I made manual edits and fixes on my own machine when things didn't run as
  expected in VS Code, rather than just accepting the first version handed to me.

## Key decisions I made

1. **Django instead of the alternative stacks discussed.** I specifically
   chose Django over other options because it gives auth, an ORM, and an
   admin interface out of the box, which maps cleanly onto the assignment's
   requirement for a login-gated dashboard - I didn't want to hand-roll
   session/auth handling for something this scoped.

2. **A single `InteractionLog` table keyed by `interaction_id`, rather than
   separate tables per command.** This was a deliberate simplification on my
   part once I understood the dedup requirement - one unique constraint on
   one table is much easier to reason about (and to demo) than per-command
   bookkeeping, and it doubles as the dashboard's live log with no extra work.

3. **A background thread for the deferred work, instead of a real task queue.**
   I decided this was an acceptable trade-off for the scope of this exercise -
   Discord's ~3 second response window forces *some* form of async handling,
   and a plain thread is honest about what it is (no broker, no retry-on-crash)
   rather than overbuilding infrastructure I wouldn't be able to fully test
   in the time available. I flagged this explicitly as a known limitation
   rather than hiding it.

## The hardest part

The trickiest thing to get right conceptually was that Discord's *interaction*
types and *response* types are two separate enums that happen to share
numbers - interaction type `5` is `MODAL_SUBMIT`, but response type `5` is
`DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE`. It would be very easy to write code
that looks correct but silently does the wrong thing depending on which enum
a bare `5` was meant to refer to. I made sure the final code names these as
two clearly separate constant sets (`INTERACTION_*` vs `RESPONSE_*`) instead
of using bare numbers anywhere, specifically so a reviewer - or me, coming
back to this in a few months - can't confuse the two.

On the practical side, the hardest bug I ran into was after logout: the
dashboard kept appearing when I pressed the browser's back button instead of
requiring a fresh login, and clicking "Log out" itself returned a blank page.
I noticed this by actually testing the login/logout flow end to end rather
than assuming it worked because the happy path (login -> dashboard) looked
fine. Once I described the exact symptom, the fix turned out to be two small,
separate things: Django's built-in logout view expects a POST request (not a
plain link), and the dashboard needed cache headers so a browser back-button
press wouldn't just replay a stale cached page instead of re-checking the
session.

I also don't have a way to run this against a live Discord app from a fully
clean machine to double check every edge case, so anyone picking this up
should treat the manual end-to-end test (which I did do, command by command,
against a real test server) as the source of truth over any assumptions in
the code comments.

## What I'd improve with more time

- Swap the background thread for a real task queue (Celery/RQ with Redis) so
  retries survive a server restart, instead of a thread that's lost if the
  process dies mid-request.
- Actually implement the `/report` **modal** (pop-up form) instead of the
  current plain string option - I decided against this for time reasons since
  the string option is functionally equivalent for this scope.
- Add per-server rate limiting on `/report` so one user can't spam the mirror
  channel.
- Write automated tests for the signature verification and dedup logic
  specifically, since those are the two places a bug would be worst (a forged
  request getting through, or a duplicate causing a double mirror-post) - right
  now my confidence in both comes from manual testing rather than a test suite.