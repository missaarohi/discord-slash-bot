import json
import logging
import threading

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpResponseForbidden, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .ai import summarize_text
from .discord_client import edit_original_response, mirror_to_discord_webhook, mirror_to_slack
from .models import CommandConfig, DiscordServer, InteractionLog
from .signature import verify_discord_signature

logger = logging.getLogger("bot")

# Discord interaction types (the payload we receive)
INTERACTION_PING = 1
INTERACTION_APPLICATION_COMMAND = 2
INTERACTION_MESSAGE_COMPONENT = 3
INTERACTION_MODAL_SUBMIT = 5

# Discord interaction *response* types (what we reply with)
RESPONSE_PONG = 1
RESPONSE_CHANNEL_MESSAGE_WITH_SOURCE = 4
RESPONSE_DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
RESPONSE_DEFERRED_UPDATE_MESSAGE = 6
RESPONSE_UPDATE_MESSAGE = 7


# ---------------------------------------------------------------------------
# Discord interactions endpoint
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def discord_interactions(request):
    """Single endpoint Discord POSTs every interaction to.

    Order of operations matters here:
      1. verify the Ed25519 signature BEFORE touching the body as JSON
      2. answer PING with PONG (required once, when the endpoint is registered)
      3. for real commands, ack fast (deferred) and do the actual work in the
         background so we never blow Discord's ~3 second window
    """
    if not verify_discord_signature(request):
        return HttpResponseForbidden("invalid request signature")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest("invalid json")

    itype = payload.get("type")

    if itype == INTERACTION_PING:
        return JsonResponse({"type": RESPONSE_PONG})

    if itype == INTERACTION_APPLICATION_COMMAND:
        return _handle_command(payload)

    if itype == INTERACTION_MESSAGE_COMPONENT:
        return _handle_component(payload)

    if itype == INTERACTION_MODAL_SUBMIT:
        return _handle_modal(payload)

    return JsonResponse({"error": "unsupported interaction type"}, status=400)


def _extract_user(payload):
    member = payload.get("member") or {}
    user = member.get("user") or payload.get("user") or {}
    user_id = user.get("id", "")
    display_name = user.get("global_name") or user.get("username") or "unknown"
    return user_id, display_name


def _handle_command(payload):
    interaction_id = payload["id"]
    interaction_token = payload["token"]
    guild_id = payload.get("guild_id", "")
    data = payload.get("data", {})
    command_name = data.get("name", "")
    user_id, display_name = _extract_user(payload)
    options = {opt["name"]: opt.get("value") for opt in data.get("options", [])}

    # --- Dedup on interaction id -------------------------------------------
    # Discord redelivers an interaction if it thinks we didn't ack it in time.
    # get_or_create with the unique constraint on interaction_id is our guard:
    # the *second* delivery finds the row already there and we just re-ack
    # without running the command logic (mirror, AI call, etc.) twice.
    log, created = InteractionLog.objects.get_or_create(
        interaction_id=interaction_id,
        defaults={
            "command_name": command_name,
            "user_discord_id": user_id,
            "user_display_name": display_name,
            "raw_payload": payload,
            "status": InteractionLog.STATUS_RECEIVED,
        },
    )
    if not created:
        logger.info("duplicate interaction %s ignored (already logged)", interaction_id)
        return JsonResponse({"type": RESPONSE_DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE})

    server = DiscordServer.objects.filter(guild_id=guild_id).first()
    if server:
        log.server = server
        log.save(update_fields=["server"])

    # Ack immediately with "deferred" so Discord shows a "thinking..." state,
    # then do the real work off-thread and patch the message in afterward.
    # This is what keeps us inside the ~3 second window even when the mirror
    # webhook or the AI call is slow or briefly down.
    thread = threading.Thread(
        target=_process_command_in_background,
        args=(log.id, server.id if server else None, command_name, options, interaction_token),
        daemon=True,
    )
    thread.start()

    return JsonResponse({"type": RESPONSE_DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE})


def _process_command_in_background(log_id, server_id, command_name, options, interaction_token):
    """Runs off the request thread. Never raises - always leaves the
    InteractionLog row in a terminal state and always tries to tell the
    user in Discord what happened, even on failure."""
    log = InteractionLog.objects.get(id=log_id)
    server = DiscordServer.objects.filter(id=server_id).first() if server_id else None
    config = CommandConfig.objects.filter(server=server, command_name=command_name).first() if server else None

    try:
        components = None

        if config and not config.is_enabled:
            reply = f"The `/{command_name}` command is turned off by this server's admin right now."
            log.action_taken = "blocked: command disabled in config"

        elif command_name == "status":
            reply = "\u2705 Bot is online and listening for commands."
            log.action_taken = "replied with status"

        elif command_name == "report":
            text = (options.get("text") or "").strip()
            flagged = bool(config and config.rule_keyword and config.rule_keyword.lower() in text.lower())
            summary = summarize_text(text) if (config and config.ai_enabled) else None

            template = config.response_template if (config and config.response_template) else "Report received: {text}"
            reply = template.format(text=text)
            if flagged:
                reply += "\n\u26a0\ufe0f Flagged: matched keyword configured by the admin."
            if summary:
                reply += f"\n\U0001f916 AI summary: {summary}"

            log.action_taken = "logged report" + (" (flagged)" if flagged else "")
            components = [
                {
                    "type": 1,  # action row
                    "components": [
                        {
                            "type": 2,  # button
                            "style": 3,  # green
                            "label": "Mark Resolved",
                            "custom_id": f"resolve:{log.id}",
                        }
                    ],
                }
            ]
        else:
            reply = f"Command `/{command_name}` isn't wired up yet."
            log.action_taken = "unknown command"

        edit_original_response(interaction_token, reply, components=components)

        if server and server.mirror_webhook_url:
            mirror_text = f"[/{command_name}] {log.user_display_name}: {options.get('text') or 'ran the command'}"
            try:
                if server.mirror_type == DiscordServer.MIRROR_SLACK:
                    mirror_to_slack(server.mirror_webhook_url, mirror_text)
                else:
                    mirror_to_discord_webhook(server.mirror_webhook_url, mirror_text)
                log.mirrored = True
            except Exception as mirror_err:  # noqa: BLE001 - downstream can be down, keep going
                log.mirrored = False
                log.error_message = f"mirror failed: {mirror_err}"
                logger.warning("mirror failed for interaction %s: %s", log.interaction_id, mirror_err)

        log.status = InteractionLog.STATUS_PROCESSED

    except Exception as e:  # noqa: BLE001 - last-resort catch so the row never hangs "received" forever
        logger.exception("failed to process interaction %s", log.interaction_id)
        log.status = InteractionLog.STATUS_FAILED
        log.error_message = str(e)
        try:
            edit_original_response(interaction_token, "\u26a0\ufe0f Something went wrong handling this command.")
        except Exception:  # noqa: BLE001
            logger.exception("also failed to notify Discord about the failure")
    finally:
        log.save()


def _handle_component(payload):
    """Handles button clicks - a second interaction type we verify the same
    way as commands, since it hits the same signed endpoint."""
    data = payload.get("data", {})
    custom_id = data.get("custom_id", "")

    if custom_id.startswith("resolve:"):
        log_id = custom_id.split(":", 1)[1]
        log = InteractionLog.objects.filter(id=log_id).first()
        if log:
            log.resolved = True
            log.save(update_fields=["resolved"])
        return JsonResponse({
            "type": RESPONSE_UPDATE_MESSAGE,
            "data": {"content": "\u2705 Marked resolved.", "components": []},
        })

    return JsonResponse({"type": RESPONSE_DEFERRED_UPDATE_MESSAGE})


def _handle_modal(payload):
    # Not wired up to a specific command in this build - see README's
    # "what I'd add with more time" for how /report would open a modal instead
    # of using a plain string option. Still verified/signed like every other
    # interaction type so a stray modal submit doesn't 500.
    return JsonResponse({"type": RESPONSE_DEFERRED_UPDATE_MESSAGE})


# ---------------------------------------------------------------------------
# Signup / Dashboard (behind Django auth login)
# ---------------------------------------------------------------------------

def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard")
    else:
        form = UserCreationForm()

    return render(request, "bot/signup.html", {"form": form})


@never_cache
@login_required
def dashboard(request):
    servers = DiscordServer.objects.filter(admin_user=request.user)
    logs = InteractionLog.objects.filter(server__in=servers).select_related("server")[:200]
    return render(request, "bot/dashboard.html", {"servers": servers, "logs": logs})


@never_cache
@login_required
def connect_server(request):
    if request.method == "POST":
        guild_id = request.POST.get("guild_id", "").strip()
        guild_name = request.POST.get("guild_name", "").strip()
        mirror_type = request.POST.get("mirror_type", DiscordServer.MIRROR_SLACK)
        mirror_webhook_url = request.POST.get("mirror_webhook_url", "").strip()

        if not guild_id:
            return render(request, "bot/connect_server.html", {"error": "Server (guild) ID is required."})

        server, _ = DiscordServer.objects.get_or_create(admin_user=request.user, guild_id=guild_id)
        server.guild_name = guild_name
        server.mirror_type = mirror_type
        if mirror_webhook_url:
            server.mirror_webhook_url = mirror_webhook_url
        server.save()

        CommandConfig.objects.get_or_create(server=server, command_name="status")
        CommandConfig.objects.get_or_create(
            server=server,
            command_name="report",
            defaults={"response_template": "Report received: {text}"},
        )
        return redirect("dashboard")

    return render(request, "bot/connect_server.html")


@never_cache
@login_required
def command_config(request, server_id):
    server = get_object_or_404(DiscordServer, id=server_id, admin_user=request.user)
    configs = CommandConfig.objects.filter(server=server)

    if request.method == "POST":
        for config in configs:
            prefix = f"cfg_{config.id}_"
            config.is_enabled = request.POST.get(prefix + "enabled") == "on"
            config.ai_enabled = request.POST.get(prefix + "ai_enabled") == "on"
            config.rule_keyword = request.POST.get(prefix + "keyword", "").strip()
            config.response_template = request.POST.get(prefix + "template", config.response_template) or config.response_template
            config.save()
        return redirect("command_config", server_id=server.id)

    return render(request, "bot/config.html", {"server": server, "configs": configs})