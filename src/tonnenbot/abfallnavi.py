"""AbfallNavi (regioit.de) API client — minimal.

AbfallNavi is the backend used by several German waste collection services,
including Kreis Gütersloh GEG (service='krwaf'). Only what the bot needs:
resolve city+street, fetch all dated collection entries, decode fraction ids
to human names.

Base URL: https://{service}-abfallapp.regioit.de/abfall-app-{service}/rest
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

import requests


log = logging.getLogger(__name__)


@dataclass
class Pickup:
    day: date
    fraktion_id: int
    fraktion_name: str


class AbfallNavi:
    def __init__(self, service: str, timeout: int = 20) -> None:
        self.service = service
        self.timeout = timeout
        self.base = f"https://{service}-abfallapp.regioit.de/abfall-app-{service}/rest"
        self._session = requests.Session()
        self._fraktionen: dict[int, str] | None = None

    def _get(self, path: str):
        r = self._session.get(f"{self.base}/{path.lstrip('/')}", timeout=self.timeout)
        r.encoding = "utf-8"
        r.raise_for_status()
        return r.json()

    def fraktionen(self) -> dict[int, str]:
        if self._fraktionen is None:
            self._fraktionen = {f["id"]: f["name"] for f in self._get("fraktionen")}
        return self._fraktionen

    def city_id(self, city: str) -> int:
        for c in self._get("orte"):
            if c["name"].lower() == city.lower():
                return c["id"]
        raise LookupError(f"city {city!r} not found in service {self.service}")

    def street_id(self, city_id: int, street: str) -> int:
        for s in self._get(f"orte/{city_id}/strassen"):
            if s["name"].lower() == street.lower():
                return s["id"]
        raise LookupError(f"street {street!r} not in city {city_id}")

    def pickups(self, street_id: int, fraktion_filter: Iterable[int] | None = None) -> list[Pickup]:
        raw = self._get(f"strassen/{street_id}/termine")
        fraktionen = self.fraktionen()
        filt = set(fraktion_filter) if fraktion_filter is not None else None
        out: list[Pickup] = []
        for t in raw:
            fid = t["bezirk"]["fraktionId"]
            if filt is not None and fid not in filt:
                continue
            out.append(Pickup(
                day=datetime.strptime(t["datum"], "%Y-%m-%d").date(),
                fraktion_id=fid,
                fraktion_name=fraktionen.get(fid, f"#{fid}"),
            ))
        out.sort(key=lambda p: p.day)
        return out
