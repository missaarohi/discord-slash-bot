"""
Run this once (and again whenever you change command definitions) to
register your slash commands with Discord:

    python scripts/register_commands.py

Reads DISCORD_APPLICATION_ID and DISCORD_BOT_TOKEN from your .env file.
Registers commands globally (can take up to an hour to propagate the first
time). For instant testing, register per-guild instead - see the commented
alternative URL below.
"""
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

APPLICATION_ID = os.environ.get("DISCORD_APPLICATION_ID")
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")

if not APPLICATION_ID or not BOT_TOKEN:
    sys.exit("Set DISCORD_APPLICATION_ID and DISCORD_BOT_TOKEN in your .env first.")

# Global commands (slow to propagate, up to ~1hr the first time):
URL = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/commands"

# For instant updates while developing, register to a single test guild instead:
# GUILD_ID = "your-test-server-id"
# URL = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/guilds/{GUILD_ID}/commands"

COMMANDS = [
    {
        "name": "status",
        "description": "Check whether the bot is online",
        "type": 1,  # CHAT_INPUT
    },
    {
        "name": "report",
        "description": "File a quick report",
        "type": 1,
        "options": [
            {
                "name": "text",
                "description": "What do you want to report?",
                "type": 3,  # STRING
                "required": True,
            }
        ],
    },
]


def main():
    resp = requests.put(
        URL,
        headers={"Authorization": f"Bot {BOT_TOKEN}"},
        json=COMMANDS,
        timeout=15,
    )
    print(resp.status_code)
    print(resp.json())
    if resp.status_code >= 300:
        sys.exit(1)


if __name__ == "__main__":
    main()
