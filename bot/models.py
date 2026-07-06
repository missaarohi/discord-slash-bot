from django.conf import settings
from django.db import models


class DiscordServer(models.Model):
    """One connected Discord guild, owned by one admin user.

    Keeping servers isolated by admin_user + guild_id is what gives us
    multi-server support: every query below is always scoped to `request.user`.
    """

    MIRROR_SLACK = "slack"
    MIRROR_DISCORD = "discord"
    MIRROR_CHOICES = [
        (MIRROR_SLACK, "Slack Incoming Webhook"),
        (MIRROR_DISCORD, "Discord Webhook (separate channel)"),
    ]

    admin_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="servers")
    guild_id = models.CharField(max_length=32)
    guild_name = models.CharField(max_length=200, blank=True)

    mirror_type = models.CharField(max_length=10, choices=MIRROR_CHOICES, default=MIRROR_SLACK)
    # Webhook URL is a secret capability URL - never log it, never render it
    # back into templates in plain text after first save (see connect_server view).
    mirror_webhook_url = models.CharField(max_length=500, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("admin_user", "guild_id")
        ordering = ["-created_at"]

    def __str__(self):
        return self.guild_name or self.guild_id


class CommandConfig(models.Model):
    """Admin-editable behavior for one slash command on one server.

    This is what makes command rules configurable in the UI instead of
    hard-coded: the interaction handler reads this row at request time.
    """

    server = models.ForeignKey(DiscordServer, on_delete=models.CASCADE, related_name="command_configs")
    command_name = models.CharField(max_length=32)
    is_enabled = models.BooleanField(default=True)

    # Simple rule: if this keyword appears in the command text, flag it.
    rule_keyword = models.CharField(max_length=200, blank=True, default="")

    # {text} gets filled in with the user's report text at runtime.
    response_template = models.TextField(default="Got it: {text}")

    ai_enabled = models.BooleanField(
        default=False,
        help_text="Run the report text through an LLM (Groq) to summarize/tag it. Requires GROQ_API_KEY.",
    )

    class Meta:
        unique_together = ("server", "command_name")

    def __str__(self):
        return f"{self.server}: /{self.command_name}"


class InteractionLog(models.Model):
    """Every Discord interaction we receive, one row each.

    `interaction_id` has a unique constraint - that's the dedup mechanism.
    If Discord redelivers the same interaction (e.g. because we were slow
    to ack), the second insert is rejected/short-circuited before we act again.
    """

    STATUS_RECEIVED = "received"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_RECEIVED, "Received"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_FAILED, "Failed"),
    ]

    interaction_id = models.CharField(max_length=64, unique=True)
    server = models.ForeignKey(DiscordServer, null=True, blank=True, on_delete=models.SET_NULL, related_name="logs")

    command_name = models.CharField(max_length=32, blank=True, default="")
    user_discord_id = models.CharField(max_length=32, blank=True, default="")
    user_display_name = models.CharField(max_length=200, blank=True, default="")

    raw_payload = models.JSONField(default=dict, blank=True)
    action_taken = models.CharField(max_length=200, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RECEIVED)
    error_message = models.TextField(blank=True, default="")

    mirrored = models.BooleanField(default=False)
    resolved = models.BooleanField(default=False)  # toggled by the "Mark Resolved" button

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.command_name} #{self.interaction_id[:8]} ({self.status})"
