"""Kinder-Routinen Punktesystem integration.

v0.2: Ein-Klick-Assistent (siehe config_flow.py) legt pro Kind einen
Eintrag an, der beliebig viele Routinen mit jeweils eigener, selbst
erzeugter To-Do-Liste enthaelt. Alle Routinen eines Kindes teilen sich
EIN Wochenpunktekonto und EIN Sparkonto.

Architektur-Unterschied zu v0.1: Die To-Do-Listen sind jetzt eine eigene
Plattform dieser Integration (siehe todo.py), keine externe Liste mehr.
Punkte werden direkt beim Abhaken innerhalb der Entity-Methode vergeben
(kein State-Change-Event-Listener mehr noetig) - dadurch ist die
Restart-Drift-Klasse von Bug, die v0.1 hatte, architektonisch
ausgeschlossen: ein HA-Neustart ruft niemals async_update_todo_item auf.
"""
from __future__ import annotations

import logging
from datetime import time as dt_time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BONUS_ENABLED,
    CONF_BONUS_POINTS,
    CONF_DASHBOARD_ID,
    CONF_DASHBOARD_URL_PATH,
    CONF_KIND_NAME,
    CONF_NOTIFY_TARGET,
    CONF_ROUTINES,
    DOMAIN,
    ROUTINE_DEADLINE,
    ROUTINE_TASKS,
    ROUTINE_WEEKDAYS,
    STORAGE_VERSION,
)
from .dashboard import async_remove_dashboard, async_setup_dashboard

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "todo"]
_WEEKDAY_MAP = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class KinderRoutinenData:
    """Haelt und persistiert den Zustand aller Routinen eines Kindes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}")
        self.wochenpunkte: int = 0
        self.punktekonto: int = 0
        # Pro Routine: {"completed": int, "points_awarded": int, "items": [...]}
        self.routine_state: list[dict] = []
        self._listeners: list = []
        # Wird von dashboard.py gesetzt, sobald ein Dashboard angelegt wurde
        self.dashboard_url_path: str | None = None
        self.dashboard_item_id: str | None = None

    @property
    def routines_config(self) -> list[dict]:
        return self.entry.data[CONF_ROUTINES]

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        self.wochenpunkte = stored.get("wochenpunkte", 0)
        self.punktekonto = stored.get("punktekonto", 0)
        self.dashboard_url_path = stored.get("dashboard_url_path")
        self.dashboard_item_id = stored.get("dashboard_item_id")
        saved_routines = stored.get("routines", [])

        self.routine_state = []
        for idx, cfg in enumerate(self.routines_config):
            saved = saved_routines[idx] if idx < len(saved_routines) else None
            items = saved.get("items") if saved else None
            if not items:
                items = [
                    {"uid": f"{idx}_{j}", "summary": task, "status": "needs_action"}
                    for j, task in enumerate(cfg[ROUTINE_TASKS])
                ]
            self.routine_state.append(
                {
                    "completed": saved.get("completed", 0) if saved else 0,
                    "points_awarded": saved.get("points_awarded", 0) if saved else 0,
                    "items": items,
                }
            )

    async def async_save(self) -> None:
        await self._store.async_save(
            {
                "wochenpunkte": self.wochenpunkte,
                "punktekonto": self.punktekonto,
                "routines": self.routine_state,
                "dashboard_url_path": self.dashboard_url_path,
                "dashboard_item_id": self.dashboard_item_id,
            }
        )

    def add_listener(self, callback) -> None:
        self._listeners.append(callback)

    def notify_listeners(self) -> None:
        for cb in self._listeners:
            cb()

    # -- Konfiguration -----------------------------------------------------

    def routine_name(self, index: int) -> str:
        return self.routines_config[index]["name"]

    def deadline(self, index: int) -> dt_time:
        raw = self.routines_config[index][ROUTINE_DEADLINE]
        h, m, *_ = raw.split(":")
        return dt_time(int(h), int(m))

    def weekdays(self, index: int) -> list[str]:
        return self.routines_config[index][ROUTINE_WEEKDAYS]

    def task_count(self, index: int) -> int:
        return len(self.routines_config[index][ROUTINE_TASKS])

    def bonus_enabled(self) -> bool:
        return self.entry.options.get(
            CONF_BONUS_ENABLED, self.entry.data.get(CONF_BONUS_ENABLED, True)
        )

    def bonus_points(self) -> int:
        return int(
            self.entry.options.get(
                CONF_BONUS_POINTS, self.entry.data.get(CONF_BONUS_POINTS, 0)
            )
        )

    def notify_target(self) -> str:
        return self.entry.options.get(
            CONF_NOTIFY_TARGET, self.entry.data.get(CONF_NOTIFY_TARGET, "notify.notify")
        )

    def kind_name(self) -> str:
        return self.entry.data[CONF_KIND_NAME]

    # -- To-Do-Items ---------------------------------------------------------

    def items(self, index: int) -> list[dict]:
        return self.routine_state[index]["items"]

    def _is_eligible_now(self, index: int) -> bool:
        now = dt_util.now()
        return (
            now.time() < self.deadline(index)
            and _WEEKDAY_MAP[now.weekday()] in self.weekdays(index)
        )

    async def async_apply_item_status(self, index: int, uid: str, status: str) -> None:
        """Wird von der To-Do-Entity bei jeder Statusaenderung aufgerufen.

        Aktualisiert den 'completed'-Zaehler immer live (fuer Anzeige/Bonus-
        Pruefung). Punkte werden nur innerhalb der Frist gutgeschrieben bzw.
        wieder abgezogen (points_awarded bleibt danach eingefroren).
        """
        state = self.routine_state[index]
        item = next((i for i in state["items"] if i["uid"] == uid), None)
        if item is None or item["status"] == status:
            return
        item["status"] = status
        state["completed"] = sum(
            1 for i in state["items"] if i["status"] == "completed"
        )

        if self._is_eligible_now(index):
            desired = min(state["completed"], self.task_count(index))
            delta = desired - state["points_awarded"]
            if delta:
                state["points_awarded"] = desired
                self.wochenpunkte = max(0, self.wochenpunkte + delta)
                self.punktekonto = max(0, self.punktekonto + delta)

        await self.async_save()
        self.notify_listeners()

    async def async_add_item(self, index: int, summary: str) -> str:
        state = self.routine_state[index]
        uid = f"{index}_{dt_util.utcnow().timestamp()}"
        state["items"].append({"uid": uid, "summary": summary, "status": "needs_action"})
        await self.async_save()
        self.notify_listeners()
        return uid

    async def async_rename_item(self, index: int, uid: str, summary: str) -> None:
        item = next((i for i in self.routine_state[index]["items"] if i["uid"] == uid), None)
        if item is not None:
            item["summary"] = summary
            await self.async_save()
            self.notify_listeners()

    async def async_delete_items(self, index: int, uids: list[str]) -> None:
        state = self.routine_state[index]
        state["items"] = [i for i in state["items"] if i["uid"] not in uids]
        state["completed"] = sum(1 for i in state["items"] if i["status"] == "completed")
        await self.async_save()
        self.notify_listeners()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richtet einen Kinder-Routinen-Eintrag (= ein Kind) ein."""
    data = KinderRoutinenData(hass, entry)
    await data.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data

    async def _nightly_reset(now) -> None:
        for idx in range(len(data.routines_config)):
            state = data.routine_state[idx]
            for item in state["items"]:
                item["status"] = "needs_action"
            state["completed"] = 0
            state["points_awarded"] = 0
        await data.async_save()
        data.notify_listeners()

    unsub_nightly = async_track_time_change(hass, _nightly_reset, hour=23, minute=59, second=0)

    async def _weekly_reset(now) -> None:
        data.wochenpunkte = 0
        await data.async_save()
        data.notify_listeners()

    unsub_weekly = async_track_time_change(hass, _weekly_reset, hour=0, minute=1, second=0)

    unsub_bonus_list = []
    for idx, cfg in enumerate(data.routines_config):
        d = data.deadline(idx)
        bonus_minute = (d.minute + 1) % 60
        bonus_hour = (d.hour + (1 if d.minute == 59 else 0)) % 24

        async def _bonus_check(now, routine_index=idx) -> None:
            if not data.bonus_enabled():
                return
            if _WEEKDAY_MAP[now.weekday()] not in data.weekdays(routine_index):
                return
            state = data.routine_state[routine_index]
            if state["completed"] < data.task_count(routine_index):
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
                    {
                        "title": "Tagesbonus 🎉",
                        "message": (
                            f"{data.kind_name()} hat die Routine "
                            f"'{data.routine_name(routine_index)}' komplett "
                            f"fristgerecht erledigt: +{bonus} Bonuspunkte!"
                        ),
                    },
                    blocking=False,
                )
            except Exception:  # noqa: BLE001 - Notify-Ziel evtl. noch nicht angepasst
                _LOGGER.warning(
                    "Konnte Tagesbonus-Benachrichtigung nicht senden (Notify-Ziel pruefen)"
                )

        unsub_bonus_list.append(
            async_track_time_change(
                hass, _bonus_check, hour=bonus_hour, minute=bonus_minute, second=0
            )
        )

    entry.async_on_unload(unsub_nightly)
    entry.async_on_unload(unsub_weekly)
    for unsub in unsub_bonus_list:
        entry.async_on_unload(unsub)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Dashboard automatisch einrichten (best effort - siehe dashboard.py)
    await async_setup_dashboard(hass, entry, data)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Wird beim endgueltigen Entfernen des Eintrags aufgerufen - raeumt
    das automatisch angelegte Dashboard mit auf, falls vorhanden."""
    await async_remove_dashboard(hass, entry)
