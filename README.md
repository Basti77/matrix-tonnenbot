# matrix-tonnenbot

Matrix bot that reminds a family room every day at a configurable time whether **tomorrow** any of the monitored waste bins will be picked up. Data source: **AbfallNavi** (regioit.de), the backend used by dozens of German waste authorities — preconfigured here for **Kreis Gütersloh GEG** (service `krwaf`).

Works for any city/street supported by AbfallNavi — see the [upstream service list](https://github.com/mampfes/hacs_waste_collection_schedule/blob/master/doc/source/abfallnavi_de.md). Change `ABFALL_SERVICE`, `ABFALL_CITY`, `ABFALL_STREET` in the env file.

## Example output

```
🗑 Morgen (Montag 20.04.) raus:
  🟡 Gelbe Tonne
```

## How it works

- **Once per day** at `CHECK_HOUR:CHECK_MINUTE` (default **15:00** local time) the bot fetches the full annual schedule from the AbfallNavi REST API, filters for tomorrow's date and the monitored fractions, and posts one message — **only if there is something to announce**. No daily "nothing today" noise.
- **Always live data.** There's no local schedule cache. If the waste authority shifts a date (public holidays, etc.) the next-day check picks it up automatically.
- **State** (last post record) under `~/.local/state/tonnenbot/last.json`.

## Monitored fractions

`WATCH_FRAKTION_IDS` (comma-separated fraction ids from AbfallNavi). Defaults cover all typical **Restmüll**, **Papier**, and **Gelbe Tonne** variants for Kreis GT:

| IDs | Meaning |
|---|---|
| 0–4 | Restabfall (weekly / 2-week / 4-week / 1.1 m³) |
| 5–7 | Bioabfall (defaults *off*) |
| 8–9 | Papiertonne |
| 10–11 | Gelbe Tonne |

Full current list for your service:

```bash
curl -s https://krwaf-abfallapp.regioit.de/abfall-app-krwaf/rest/fraktionen | jq
```

## Install

```bash
cd ~
git clone https://github.com/Basti77/matrix-tonnenbot.git
python3 -m venv ~/.local/venvs/tonnenbot
~/.local/venvs/tonnenbot/bin/pip install -e ~/matrix-tonnenbot
```

Create a Matrix user (Synapse shared-secret example):

```bash
docker exec matrix-synapse register_new_matrix_user \
  -c /data/homeserver.yaml http://localhost:8008 \
  -u tonnenbot -p "$(openssl rand -base64 18)" --no-admin
```

Login once to get an access token:

```bash
curl -sS -X POST http://127.0.0.1:8008/_matrix/client/v3/login \
  -H 'Content-Type: application/json' \
  -d '{"type":"m.login.password","identifier":{"type":"m.id.user","user":"tonnenbot"},"password":"<PASS>","device_id":"TONNENBOT"}'
```

Store secrets in `~/.tonnenbot-secrets/tonnenbot.env` (mode 600) — see [`tonnenbot.env.example`](tonnenbot.env.example).

Invite the bot into the target room, then enable the systemd-user unit:

```bash
mkdir -p ~/.config/systemd/user
cp ~/matrix-tonnenbot/systemd/tonnenbot.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now tonnenbot.service
journalctl --user -u tonnenbot -f
```

Make sure `loginctl enable-linger $USER` is set so the unit survives logouts.

## Testing the setup

Set `POST_ON_STARTUP=1` (and optionally `STARTUP_FORCE_TODAY=1`) in the env to force an immediate post on service restart — useful during initial wiring. **Switch back to `POST_ON_STARTUP=0` for production**, otherwise every Service restart / reboot would re-post tomorrow's forecast.

The helper `test-trigger.sh` restarts the service and tails the last 30 log lines.

## License

MIT. API data © regioit.de / respective municipal waste authorities; this is a thin client for public endpoints.
