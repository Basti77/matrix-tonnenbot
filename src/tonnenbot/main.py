"""tonnenbot — daily check at 15:00 for tomorrow's pickups, Matrix message if any match.

Config via env (see tonnenbot.env.example). Monitored fractions default to
Restmüll, Papiertonne, Gelbe Tonne. Sends one compact message per day, only
if at least one monitored bin is scheduled for the next day.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .abfallnavi import AbfallNavi, Pickup
from .matrix_sender import SimpleMatrixSender


log = logging.getLogger("tonnenbot")

TZ = ZoneInfo("Europe/Berlin")

# Fraktion-IDs der AbfallNavi-Krwaf-Instanz (Kreis Gütersloh GEG)
# Restmüll = alle Rest-Varianten; Papier = 8,9; Gelbe = 10,11
DEFAULT_WATCH_IDS = {0, 1, 2, 3, 4, 8, 9, 10, 11}

ICON = {
    "rest": "⚫",
    "papier": "🟦",
    "gelb": "🟡",
}


def _icon_for(name: str) -> str:
    n = name.lower()
    if "papier" in n:
        return ICON["papier"]
    if "gelb" in n:
        return ICON["gelb"]
    return ICON["rest"]


def _env(k: str, default: str | None = None, required: bool = False) -> str:
    v = os.environ.get(k, default)
    if required and not v:
        raise SystemExit(f"env {k} required")
    return v  # type: ignore[return-value]


def _format_message(pickups: list[Pickup], for_day: date) -> str:
    weekday = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"][for_day.weekday()]
    head = f"🗑 Morgen ({weekday} {for_day.strftime('%d.%m.')}) raus:"
    lines = [head]
    for p in pickups:
        lines.append(f"  {_icon_for(p.fraktion_name)} {p.fraktion_name}")
    return "\n".join(lines)


async def _check_and_post(sender: SimpleMatrixSender, cfg: dict, *, force_today: bool = False) -> None:
    target = date.today() if force_today else (datetime.now(TZ).date() + timedelta(days=1))
    try:
        navi = AbfallNavi(cfg["service"])
        city_id = navi.city_id(cfg["city"])
        street_id = navi.street_id(city_id, cfg["street"])
        all_pickups = navi.pickups(street_id, fraktion_filter=cfg["watch_ids"])
    except Exception as e:
        log.exception("abfallnavi fetch failed: %s", e)
        return

    tomorrow = [p for p in all_pickups if p.day == target]
    if not tomorrow:
        log.info("no monitored pickup on %s — skipping", target)
        return

    # dedup by (date, fraktion_name)
    seen = set()
    uniq: list[Pickup] = []
    for p in tomorrow:
        key = (p.day, p.fraktion_name)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)

    msg = _format_message(uniq, target)
    log.info("posting:\n%s", msg)
    try:
        await sender.send_text(cfg["room_id"], msg)
    except Exception as e:
        log.exception("matrix send failed: %s", e)

    state_dir = Path(cfg["state_dir"])
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "last.json").write_text(json.dumps({
        "ts": datetime.now(TZ).isoformat(),
        "for_day": str(target),
        "message": msg,
    }))


async def _async_main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )
    watch = os.environ.get("WATCH_FRAKTION_IDS", "")
    watch_ids = set(int(x) for x in watch.split(",") if x.strip()) if watch.strip() else DEFAULT_WATCH_IDS

    cfg = {
        "homeserver": _env("MATRIX_HOMESERVER", required=True),
        "user_id": _env("MATRIX_USER_ID", required=True),
        "access_token": _env("MATRIX_ACCESS_TOKEN", required=True),
        "device_id": _env("MATRIX_DEVICE_ID", "TONNENBOT"),
        "room": _env("MATRIX_ROOM", required=True),
        "service": _env("ABFALL_SERVICE", "krwaf"),
        "city": _env("ABFALL_CITY", required=True),
        "street": _env("ABFALL_STREET", required=True),
        "watch_ids": watch_ids,
        "check_hour": int(_env("CHECK_HOUR", "15")),
        "check_minute": int(_env("CHECK_MINUTE", "0")),
        "post_on_startup": _env("POST_ON_STARTUP", "1") == "1",
        "startup_force_today": _env("STARTUP_FORCE_TODAY", "0") == "1",
        "state_dir": _env("STATE_DIR", str(Path.home() / ".local/state/tonnenbot")),
    }

    sender = SimpleMatrixSender(
        cfg["homeserver"], cfg["user_id"], cfg["access_token"], cfg["device_id"]
    )
    await sender.connect()

    room_id = cfg["room"]
    if room_id.startswith("#"):
        rid = await sender.resolve_alias(room_id)
        if rid:
            room_id = rid
    await sender.join(room_id)
    cfg["room_id"] = room_id
    log.info("tonnenbot room: %s", room_id)

    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(
        _check_and_post, "cron",
        hour=cfg["check_hour"], minute=cfg["check_minute"],
        args=[sender, cfg],
        id="daily-check", coalesce=True, misfire_grace_time=600,
    )
    scheduler.start()

    if cfg["post_on_startup"]:
        await _check_and_post(sender, cfg, force_today=cfg["startup_force_today"])

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for s in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(s, stop.set)
    log.info("tonnenbot up — daily check at %02d:%02d %s", cfg["check_hour"], cfg["check_minute"], TZ.key)
    await stop.wait()

    scheduler.shutdown(wait=False)
    await sender.close()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
