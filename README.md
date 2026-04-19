# matrix-tonnenbot

Matrix bot that reminds a family room every day at a configurable time whether **tomorrow** any of the monitored waste bins will be picked up. Data source: **AbfallNavi** (regioit.de), the backend used by dozens of German waste authorities — preconfigured here for **Kreis Gütersloh GEG** (service `krwaf`).

Works for any city/street supported by AbfallNavi — see the [upstream service list](https://github.com/mampfes/hacs_waste_collection_schedule/blob/master/doc/source/abfallnavi_de.md). Change `ABFALL_SERVICE`, `ABFALL_CITY`, `ABFALL_STREET` in the env file.

## Example output

```
🗑 Morgen (Montag 20.04.) raus:
  🟡 Gelbe Tonne
```

## Features

- **Only talks when relevant** — no daily "nothing today" noise
- **Scheduler:** daily at `CHECK_HOUR:CHECK_MINUTE` (default 15:00 local time)
- **Monitored bins** via `WATCH_FRAKTION_IDS` (comma list); defaults cover Restmüll + Papier + Gelbe Tonne
- **Startup-post** for testing, togglable with `POST_ON_STARTUP` and `STARTUP_FORCE_TODAY`
- **State** (last post) under `~/.local/state/tonnenbot/last.json`

## Fraction IDs (Kreis GT / AbfallNavi `krwaf`)

| ID | Name |
|---:|---|
| 0-4 | Restabfall-Varianten |
| 5-7 | Bioabfall (defaults *off*) |
| 8-9 | Papiertonne |
| 10-11 | Gelbe Tonne |

Full list: query `https://krwaf-abfallapp.regioit.de/abfall-app-krwaf/rest/fraktionen`.

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

Store secrets in `~/.tonnenbot-secrets/tonnenbot.env` (mode 600), see [`tonnenbot.env.example`](tonnenbot.env.example).

Invite the bot into the target room. Enable the systemd-user unit:

```bash
mkdir -p ~/.config/systemd/user
cp ~/matrix-tonnenbot/systemd/tonnenbot.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now tonnenbot.service
journalctl --user -u tonnenbot -f
```

Make sure `loginctl enable-linger $USER` is set so the unit survives logouts.

## License

MIT. API data © regioit.de / respective municipal waste authorities; this is a thin client for public endpoints.
