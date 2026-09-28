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

v1.0: Aufgabenbilder (siehe images.py) + Verwaltungs-Options-Flow zum
nachtraeglichen Hinzufuegen/Entfernen/Bearbeiten von Routinen und
Aufgaben (siehe options_flow.py). Wichtige Architekturentscheidung dafuer:
der persistente Store (KinderRoutinenData._store) ist ab v1.0 fuer alles
Routinen-/Aufgaben-Bezogene (Name, Frist, Wochentage, Aufgaben, Bilder)
die QUELLE DER WAHRHEIT, sobald eine Routine einmal geladen wurde -
entry.data[CONF_ROUTINES] ist nur noch der einmalige Startzustand bei der
Ersteinrichtung bzw. beim Hinzufuegen einer neuen Routine. So ueberleben
nachtraegliche Aenderungen einen Neuladevorgang (z. B. nach dem Hinzufuegen
oder Entfernen einer anderen Routine).
"""
from __future__ import annotations

import logging
from datetime import time as dt_time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    CONF_BONUS_ENABLED,
    CONF_BONUS_POINTS,
    CONF_DASHBOARD_ID,
    CONF_DASHBOARD_URL_PATH,
    CONF_KIND_NAME,
    CONF_NOTIFY_TARGET,
    CONF_ROUTINES,
    DOMAIN,
    ROUTINE_BASE_IMAGE,
    ROUTINE_DEADLINE,
    ROUTINE_DONE_IMAGE,
    ROUTINE_NAME,
    ROUTINE_TASK_IMAGES,
    ROUTINE_TASKS,
    ROUTINE_WEEKDAYS,
    STORAGE_VERSION,
)
from .dashboard import async_remove_dashboard, async_setup_dashboard
from .images import async_delete_image, async_delete_kind_images

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
        # Pro Routine: {"name","deadline","weekdays","base_image","done_image",
        #               "completed","points_awarded","items":[...]}
        # -> ab v1.0 die Quelle der Wahrheit fuer alles Routinen-Bezogene.
        self.routine_state: list[dict] = []
        self._listeners: list = []
        # Wird von dashboard.py gesetzt, sobald ein Dashboard angelegt wurde
        self.dashboard_url_path: str | None = None
        self.dashboard_item_id: str | None = None

    @property
    def routines_config(self) -> list[dict]:
        """Der beim Setup/Hinzufuegen hinterlegte STARTZUSTAND der Routinen.

        Nur zur Bestimmung von Anzahl/Reihenfolge der Routinen und als
        Ausgangswert beim allerersten Laden einer Routine relevant - siehe
        Modul-Docstring. Fuer laufenden Betrieb immer die Accessor-Methoden
        unten (routine_name/deadline/weekdays/task_count/...) verwenden,
        NIEMALS direkt aus diesem Property lesen.
        """
        return self.entry.data[CONF_ROUTINES]

    @property
    def kind_slug(self) -> str:
        return slugify(self.kind_name())

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
            if saved is None:
                # Brandneue Routine (Ersteinrichtung oder per Options-Flow
                # frisch hinzugefuegt) - aus der Konfiguration erzeugen.
                task_images = cfg.get(ROUTINE_TASK_IMAGES) or []
                items = [
                    {
                        "uid": f"{idx}_{j}",
                        "summary": task,
                        "status": "needs_action",
                        "image": task_images[j] if j < len(task_images) else None,
                        "completed_at": None,
                    }
                    for j, task in enumerate(cfg[ROUTINE_TASKS])
                ]
                self.routine_state.append(
                    {
                        "name": cfg[ROUTINE_NAME],
                        "deadline": cfg[ROUTINE_DEADLINE],
                        "weekdays": cfg[ROUTINE_WEEKDAYS],
                        "base_image": cfg.get(ROUTINE_BASE_IMAGE),
                        "done_image": cfg.get(ROUTINE_DONE_IMAGE),
                        "completed": 0,
                        "points_awarded": 0,
                        "items": items,
                    }
                )
            else:
                # Bestehende Routine - fehlende Felder (Migration von einer
                # aelteren Version) aus der urspruenglichen Konfiguration
                # nachtragen, gespeicherter Stand hat sonst immer Vorrang.
                items = saved.get("items") or [
                    {
                        "uid": f"{idx}_{j}",
                        "summary": task,
                        "status": "needs_action",
                        "image": None,
                        "completed_at": None,
                    }
                    for j, task in enumerate(cfg[ROUTINE_TASKS])
                ]
                for item in items:
                    item.setdefault("image", None)
                    item.setdefault("completed_at", None)
                self.routine_state.append(
                    {
                        "name": saved.get("name", cfg[ROUTINE_NAME]),
                        "deadline": saved.get("deadline", cfg[ROUTINE_DEADLINE]),
                        "weekdays": saved.get("weekdays", cfg[ROUTINE_WEEKDAYS]),
                        "base_image": saved.get("base_image", cfg.get(ROUTINE_BASE_IMAGE)),
                        "done_image": saved.get("done_image", cfg.get(ROUTINE_DONE_IMAGE)),
                        "completed": saved.get("completed", 0),
                        "points_awarded": saved.get("points_awarded", 0),
                        "items": items,
                    }
                )

        # Migration/neu erzeugte Felder direkt persistieren, damit sie beim
        # naechsten Laden schon als "saved" erkannt werden.
        await self.async_save()

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

    # -- Konfiguration (liest ab v1.0 immer aus routine_state) -------------

    def routine_count(self) -> int:
        return len(self.routine_state)

    def routine_name(self, index: int) -> str:
        return self.routine_state[index]["name"]

    def deadline(self, index: int) -> dt_time:
        raw = self.routine_state[index]["deadline"]
        h, m, *_ = raw.split(":")
        return dt_time(int(h), int(m))

    def deadline_str(self, index: int) -> str:
        return self.routine_state[index]["deadline"]

    def weekdays(self, index: int) -> list[str]:
        return self.routine_state[index]["weekdays"]

    def task_count(self, index: int) -> int:
        return len(self.routine_state[index]["items"])

    def base_image(self, index: int) -> str | None:
        return self.routine_state[index].get("base_image")

    def done_image(self, index: int) -> str | None:
        return self.routine_state[index].get("done_image")

    def has_any_image(self, index: int) -> bool:
        state = self.routine_state[index]
        if state.get("base_image") or state.get("done_image"):
            return True
        return any(i.get("image") for i in state["items"])

    def current_image_info(self, index: int) -> tuple[str | None, str]:
        """Ermittelt, welches Bild fuer die Routine gerade passend ist -
        exakt die gleiche Logik wie Niks urspruengliche YAML-Automation
        ("Bild aktualisieren"): Alles-erledigt-Bild wenn fertig, sonst das
        Bild der zuletzt abgehakten Aufgabe (mit Bild), sonst das Grundbild.
        """
        state = self.routine_state[index]
        items = state["items"]
        total = len(items)
        done_count = sum(1 for i in items if i["status"] == "completed")

        if total > 0 and done_count == total and state.get("done_image"):
            return state["done_image"], "Alles erledigt"

        candidates = [
            i for i in items if i["status"] == "completed" and i.get("image") and i.get("completed_at")
        ]
        if candidates:
            latest = max(candidates, key=lambda i: i["completed_at"])
            return latest["image"], latest["summary"]

        return state.get("base_image"), "Start"

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
        Pruefung/aktuelles Bild). Punkte werden nur innerhalb der Frist
        gutgeschrieben bzw. wieder abgezogen (points_awarded bleibt danach
        eingefroren).
        """
        state = self.routine_state[index]
        item = next((i for i in state["items"] if i["uid"] == uid), None)
        if item is None or item["status"] == status:
            return
        item["status"] = status
        item["completed_at"] = dt_util.utcnow().timestamp() if status == "completed" else None
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

    async def async_add_item(self, index: int, summary: str, image: str | None = None) -> str:
        state = self.routine_state[index]
        uid = f"{index}_{dt_util.utcnow().timestamp()}"
        state["items"].append(
            {"uid": uid, "summary": summary, "status": "needs_action", "image": image, "completed_at": None}
        )
        await self.async_save()
        self.notify_listeners()
        return uid

    async def async_rename_item(self, index: int, uid: str, summary: str) -> None:
        item = next((i for i in self.routine_state[index]["items"] if i["uid"] == uid), None)
        if item is not None:
            item["summary"] = summary
            await self.async_save()
            self.notify_listeners()

    async def async_set_item_image(self, index: int, uid: str, image: str | None) -> None:
        item = next((i for i in self.routine_state[index]["items"] if i["uid"] == uid), None)
        if item is not None:
            old_image = item.get("image")
            item["image"] = image
            await self.async_save()
            self.notify_listeners()
            if old_image and old_image != image:
                await async_delete_image(self.hass, old_image)

    async def async_delete_items(self, index: int, uids: list[str]) -> None:
        state = self.routine_state[index]
        removed = [i for i in state["items"] if i["uid"] in uids]
        state["items"] = [i for i in state["items"] if i["uid"] not in uids]
        state["completed"] = sum(1 for i in state["items"] if i["status"] == "completed")
        await self.async_save()
        self.notify_listeners()
        for item in removed:
            if item.get("image"):
                await async_delete_image(self.hass, item["image"])

    # -- Routinen verwalten (Options-Flow) ----------------------------------

    async def async_update_routine_meta(
        self,
        index: int,
        *,
        name: str | None = None,
        deadline: str | None = None,
        weekdays: list[str] | None = None,
    ) -> None:
        state = self.routine_state[index]
        if name is not None:
            state["name"] = name
        if deadline is not None:
            state["deadline"] = deadline
        if weekdays is not None:
            state["weekdays"] = weekdays
        await self.async_save()
        self.notify_listeners()

    async def async_set_routine_image(
        self, index: int, which: str, image: str | None
    ) -> None:
        """which: 'base_image' oder 'done_image'."""
        state = self.routine_state[index]
        old_image = state.get(which)
        state[which] = image
        await self.async_save()
        self.notify_listeners()
        if old_image and old_image != image:
            await async_delete_image(self.hass, old_image)

    async def async_append_routine(self, routine_state_entry: dict) -> None:
        """Haengt eine neu (per Options-Flow) angelegte Routine an - der
        Aufrufer sorgt zusaetzlich dafuer, dass entry.data[CONF_ROUTINES]
        um den gleichen Startzustand ergaenzt und danach ein Reload
        ausgeloest wird, damit die neuen Entities entstehen.
        """
        self.routine_state.append(routine_state_entry)
        await self.async_save()

    async def async_pop_routine(self, index: int) -> dict:
        """Entfernt eine Routine aus dem Store (inkl. Aufraeumen ihrer
        Bilder) und gibt den entfernten Zustand zurueck. Der Aufrufer sorgt
        zusaetzlich dafuer, dass entry.data[CONF_ROUTINES] passend gekuerzt
        und danach ein Reload ausgeloest wird.
        """
        state = self.routine_state.pop(index)
        await self.async_save()
        for item in state["items"]:
            if item.get("image"):
                await async_delete_image(self.hass, item["image"])
        if state.get("base_image"):
            await async_delete_image(self.hass, state["base_image"])
        if state.get("done_image"):
            await async_delete_image(self.hass, state["done_image"])
        return state


async def _async_cleanup_orphaned_entities(
    hass: HomeAssistant, entry: ConfigEntry, new_routine_count: int
) -> None:
    """Nach dem Entfernen einer Routine ruecken die Positionen der
    dahinterliegenden Routinen eine Stelle auf (die Entity-unique_ids sind
    positionsbasiert, aus Kompatibilitaetsgruenden zu v0.1/v0.2 - siehe
    sensor.py/todo.py). Dadurch wird beim naechsten Setup der oberste,
    jetzt nicht mehr existierende Index NICHT neu erzeugt und bleibt sonst
    als Karteileiche in der Entity-Registry zurueck. Diese Funktion
    entfernt genau diese verwaisten Entities."""
    registry = er.async_get(hass)
    suffixes = [
        f"_todo_{new_routine_count}",
        f"_punkte_heute_{new_routine_count}",
        f"_tagesmax_{new_routine_count}",
        f"_bild_{new_routine_count}",
    ]
    prefix = entry.entry_id
    for entity_id, entry_reg in list(registry.entities.items()):
        if entry_reg.config_entry_id != entry.entry_id:
            continue
        if entry_reg.unique_id and any(
            entry_reg.unique_id == f"{prefix}{suffix}" for suffix in suffixes
        ):
            registry.async_remove(entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Richtet einen Kinder-Routinen-Eintrag (= ein Kind) ein."""
    data = KinderRoutinenData(hass, entry)
    await data.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data

    async def _nightly_reset(now) -> None:
        for idx in range(data.routine_count()):
            state = data.routine_state[idx]
            for item in state["items"]:
                item["status"] = "needs_action"
                item["completed_at"] = None
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
    for idx in range(data.routine_count()):
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
                        "title": "Tagesbonus \U0001f389",
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
    das automatisch angelegte Dashboard sowie alle hochgeladenen Bilder
    dieses Kindes mit auf."""
    await async_remove_dashboard(hass, entry)
    kind_name = entry.data.get(CONF_KIND_NAME)
    if kind_name:
        await async_delete_kind_images(hass, slugify(kind_name))
