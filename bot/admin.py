from django.contrib import admin

from .models import CommandConfig, DiscordServer, InteractionLog


@admin.register(DiscordServer)
class DiscordServerAdmin(admin.ModelAdmin):
    list_display = ("guild_name", "guild_id", "admin_user", "mirror_type", "created_at")
    # Never list mirror_webhook_url in list_display / search - it's a secret capability URL.


@admin.register(CommandConfig)
class CommandConfigAdmin(admin.ModelAdmin):
    list_display = ("server", "command_name", "is_enabled", "ai_enabled")


@admin.register(InteractionLog)
class InteractionLogAdmin(admin.ModelAdmin):
    list_display = ("command_name", "user_display_name", "server", "status", "mirrored", "resolved", "created_at")
    list_filter = ("status", "command_name", "mirrored")
    readonly_fields = ("interaction_id", "raw_payload", "created_at", "updated_at")
