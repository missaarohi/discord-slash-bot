import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DiscordServer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("guild_id", models.CharField(max_length=32)),
                ("guild_name", models.CharField(blank=True, max_length=200)),
                (
                    "mirror_type",
                    models.CharField(
                        choices=[("slack", "Slack Incoming Webhook"), ("discord", "Discord Webhook (separate channel)")],
                        default="slack",
                        max_length=10,
                    ),
                ),
                ("mirror_webhook_url", models.CharField(blank=True, default="", max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "admin_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="servers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("admin_user", "guild_id")},
            },
        ),
        migrations.CreateModel(
            name="CommandConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("command_name", models.CharField(max_length=32)),
                ("is_enabled", models.BooleanField(default=True)),
                ("rule_keyword", models.CharField(blank=True, default="", max_length=200)),
                ("response_template", models.TextField(default="Got it: {text}")),
                (
                    "ai_enabled",
                    models.BooleanField(
                        default=False,
                        help_text="Run the report text through an LLM (Groq) to summarize/tag it. Requires GROQ_API_KEY.",
                    ),
                ),
                (
                    "server",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="command_configs",
                        to="bot.discordserver",
                    ),
                ),
            ],
            options={
                "unique_together": {("server", "command_name")},
            },
        ),
        migrations.CreateModel(
            name="InteractionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("interaction_id", models.CharField(max_length=64, unique=True)),
                ("command_name", models.CharField(blank=True, default="", max_length=32)),
                ("user_discord_id", models.CharField(blank=True, default="", max_length=32)),
                ("user_display_name", models.CharField(blank=True, default="", max_length=200)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("action_taken", models.CharField(blank=True, default="", max_length=200)),
                (
                    "status",
                    models.CharField(
                        choices=[("received", "Received"), ("processed", "Processed"), ("failed", "Failed")],
                        default="received",
                        max_length=20,
                    ),
                ),
                ("error_message", models.TextField(blank=True, default="")),
                ("mirrored", models.BooleanField(default=False)),
                ("resolved", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "server",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="logs",
                        to="bot.discordserver",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
