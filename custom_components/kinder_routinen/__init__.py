"""Kinder-Routinen Punktesystem integration.

v0.1 Funktionsumfang (siehe README-Roadmap fuer geplante Erweiterungen):
- Live-Punktevergabe beim Abhaken vor der Frist (ersetzt den Blueprint)
- Naechtlicher Reset der To-Do-Liste + Tages-Tracker
- Woechentlicher Reset des Wochenzaehlers
- Tagesbonus bei komplett fristgerechtem Tag
Noch NICHT enthalten: mehrere Routinen auf ein gemeinsames Punktekonto,
Belohnungs-Select/Button, Wochenbericht, eigene Lovelace-Karte.
"""
from __future__ import annotations

import logging
from datetime import time as dt_time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BONUS_POINTS,
    CONF_DEADLINE,
    CONF_NOTIFY_TARGET,
    CONF_TASK_COUNT,
    CONF_TODO_ENTITY,
    CONF_WEEKDAYS,
    DOMAIN,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]
_WEEKDAY_MAP = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class KinderRoutinenData:
    """Haelt und persistiert den Punktestand einer Config-Entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}")
        self.heute_erledigt: int = 0
        self.wochenpunkte: int = 0
        self.punktekonto: int = 0
        self._listeners: list = []

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self.heute_erledigt = stored.get("heute_erledigt", 0)
            self.wochenpunkte = stored.get("wochenpunkte", 0)
            self.punktekonto = stored.get("punktekonto", 0)

    async def async_save(self) -> None:
        await self._store.async_save(
            {
                "heute_erledigt": self.heute_erledigt,
                "wochenpunkte": self.wochenpunkte,
                "punktekonto": self.punktekonto,
            }
        )

    def add_listener(self, callback) -> None:
        self._listeners.append(callback)

    def notify_listeners(self) -> None:
        for cb in self._listeners:
            cb()

    def deadline(self) -> dt_time:
        raw = self.entry.options.get(CONF_DEADLINE, self.entry.data[CONF_DEADLINE])
        h, m, *_ = raw.split(":")
        return dt_time(int(h), int(m))

    def weekdays(self) -> list[str]:
        return self.entry.options.get(CONF_WEEKDAYS, self.entry.data[CONF_WEEKDAYS])

    def bonus_points(self) -> int:
        return int(self.entry.options.get(CONF_BONUS_POINTS, self.entry.data[CONF_BONUS_POINTS]))

    def notify_target(self) -> str:
        return self.entry.options.get(CONF_NOTIFY_TARGET, self.entry.data[CONF_NOTIFY_TARGET])


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richtet eine Kinder-Routinen-Punktesystem Config-Entry ein."""
    data = KinderRoutinenData(hass, entry)
    await data.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data

    todo_entity = entry.data[CONF_TODO_ENTITY]
    max_aufgaben = entry.data[CONF_TASK_COUNT]

    async def _handle_todo_change(event: Event[EventStateChangedData]) -> None:
        old = event.data["old_state"]
        new = event.data["new_state"]
        if new is None:
            return
        if old is None or old.state in (None, "unknown", "unavailable"):
            # Kein echter Vorher-Zustand vorhanden (z. B. direkt nach einem
            # Neustart/Reload) - kein Delta berechnen, sonst wuerde jeder
            # Neustart faelschlich Punkte gutschreiben. Der persistierte
            # Punktestand bleibt einfach unveraendert.
            return
        now = dt_util.now()
        if now.time() >= data.deadline():
            return
        if _WEEKDAY_MAP[now.weekday()] not in data.weekdays():
            return
        try:
            alt = int(old.state)
            neu = int(new.state)
        except ValueError:
            return
        delta = alt - neu
        if delta == 0:
            return
        neu_wert = max(0, min(data.heute_erledigt + delta, max_aufgaben))
        angewendet = neu_wert - data.heute_erledigt
        if angewendet == 0:
            return
        data.heute_erledigt = neu_wert
        data.wochenpunkte += angewendet
        data.punktekonto += angewendet
        await data.async_save()
        data.notify_listeners()

    unsub_state = async_track_state_change_event(hass, [todo_entity], _handle_todo_change)

    async def _nightly_reset(now) -> None:
        try:
            response = await hass.services.async_call(
                "todo",
                "get_items",
                {"entity_id": todo_entity, "status": "completed"},
                blocking=True,
                return_response=True,
            )
            items = response[todo_entity]["items"]
        except Exception:  # noqa: BLE001
            items = []
        for item in items:
            await hass.services.async_call(
                "todo",
                "update_item",
                {"entity_id": todo_entity, "item": item["summary"], "status": "needs_action"},
                blocking=True,
            )
        data.heute_erledigt = 0
        await data.async_save()
        data.notify_listeners()

    unsub_nightly = async_track_time_change(hass, _nightly_reset, hour=23, minute=59, second=0)

    async def _weekly_reset(now) -> None:
        data.wochenpunkte = 0
        await data.async_save()
        data.notify_listeners()

    unsub_weekly = async_track_time_change(hass, _weekly_reset, hour=0, minute=1, second=0)

    async def _bonus_check(now) -> None:
        if _WEEKDAY_MAP[now.weekday()] not in data.weekdays():
            return
        if data.heute_erledigt < max_aufgaben:
            return
        bonus = data.bonus_points()
        if bonus <= 0:
            return
        data.wochenpunkte += bonus
        data.punktekonto += bonus
        await data.async_save()
        data.notify_listeners()
        target = data.notify_target()
        service = target.split(".", 1)[1] if "." in target else "notify"
        try:
            await hass.services.async_call(
                "notify",
                service,
                {"title": "Tagesbonus 🎉", "message": f"Bonus erhalten: +{bonus} Punkte"},
                blocking=False,
            )
        except Exception:  # noqa: BLE001 - Notify-Ziel evtl. noch nicht angepasst
            _LOGGER.warning("Konnte Tagesbonus-Benachrichtigung nicht senden (Notify-Ziel pruefen)")

    d = data.deadline()
    bonus_minute = (d.minute + 1) % 60
    bonus_hour = (d.hour + (1 if d.minute == 59 else 0)) % 24
    unsub_bonus = async_track_time_change(
        hass, _bonus_check, hour=bonus_hour, minute=bonus_minute, second=0
    )

    entry.async_on_unload(unsub_state)
    entry.async_on_unload(unsub_nightly)
    entry.async_on_unload(unsub_weekly)
    entry.async_on_unload(unsub_bonus)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
