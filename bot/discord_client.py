"""
Small wrapper around the bits of the Discord REST API we need:
- editing the deferred "..." placeholder into the real reply
- posting a follow-up message
- sending a button-updated message
- mirroring a notification to Slack or a second Discord channel

All of this uses either the interaction token (short-lived, no secret needed)
or the bot token (from settings/env - never hard-coded, never logged).
"""
import logging

import requests

from django.conf import settings

logger = logging.getLogger("bot")

DISCORD_API = "https://discord.com/api/v10"
REQUEST_TIMEOUT = 10  # seconds - keep these calls snappy, they run in a background thread


def edit_original_response(interaction_token: str, content: str, components: list | None = None):
    """Replace the deferred placeholder with the real reply."""
    url = f"{DISCORD_API}/webhooks/{settings.DISCORD_APPLICATION_ID}/{interaction_token}/messages/@original"
    payload = {"content": content}
    if components is not None:
        payload["components"] = components
    resp = requests.patch(url, json=payload, timeout=REQUEST_TIMEOUT)
    if resp.status_code >= 300:
        logger.warning("edit_original_response failed: %s %s", resp.status_code, resp.text)
    return resp


def post_followup(interaction_token: str, content: str):
    url = f"{DISCORD_API}/webhooks/{settings.DISCORD_APPLICATION_ID}/{interaction_token}"
    resp = requests.post(url, json={"content": content}, timeout=REQUEST_TIMEOUT)
    if resp.status_code >= 300:
        logger.warning("post_followup failed: %s %s", resp.status_code, resp.text)
    return resp


def mirror_to_slack(webhook_url: str, text: str):
    resp = requests.post(webhook_url, json={"text": text}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp


def mirror_to_discord_webhook(webhook_url: str, text: str):
    resp = requests.post(webhook_url, json={"content": text}, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp
