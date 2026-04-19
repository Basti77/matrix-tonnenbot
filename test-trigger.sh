#!/usr/bin/env bash
# Trigger a fresh startup-post of tonnenbot (after you invited the bot).
# - Restarts the service, which does: sync → accept invite → join → post.
set -euo pipefail
systemctl --user restart tonnenbot.service
sleep 6
journalctl --user -u tonnenbot --since "15 seconds ago" --no-pager | tail -30
