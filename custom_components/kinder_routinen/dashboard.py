"""Automatische Dashboard-Einrichtung fuer Kinder-Routinen Punktesystem.

v0.2: Nach dem Setup-Assistenten wird versucht, direkt ein eigenes
Dashboard in der Seitenleiste zu registrieren (Storage-Modus, wie ein von
Hand ueber die UI angelegtes Dashboard) - inklusive Todo-Listen-Karten pro
Routine und Gauges fuer Punkte heute/Wochenpunkte/Punktekonto. Dafuer wird
dieselbe interne Speicher- und Registrierungslogik genutzt, die die
lovelace-Komponente selbst verwendet ("lovelace_dashboards"-Store +
per-Dashboard "lovelace.<id>"-Store + Panel-Registrierung).

Diese Mechanik ist NICHT als oeffentliche API fuer Custom-Integrationen
dokumentiert und kann sich zwischen HA-Versionen aendern. Deshalb ist
alles hier defensiv in try/except gekapselt: schlaegt die automatische
Registrierung fehl, wird ersatzweise eine fertige Dashboard-YAML-Datei
erzeugt und der Nutzer per persistent_notification auf die manuelle
2-Klick-Einrichtung hingewiesen. Die Einrichtung des restlichen
Integrationsumfangs (Punktevergabe, To-Do-Listen, Sensoren) ist von einem
Fehlschlag hier vollstaendig unabhaengig.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)


def _build_lovelace_config(hass: HomeAssistant, entry: ConfigEntry, data) -> dict[str, Any]:
    """Baut die Karten anhand der tatsaechlich vergebenen Entity-IDs."""
    cards: list[dict[str, Any]] = []

    for idx, cfg in enumerate(data.routines_config):
        todo_entity = _entity_id(hass, "todo", f"{entry.entry_id}_todo_{idx}")
        punkte_entity = _entity_id(hass, "sensor", f"{entry.entry_id}_punkte_heute_{idx}")
        if todo_entity:
            cards.append(
                {
                    "type": "todo-list",
                    "entity": todo_entity,
                    "title": cfg["name"],
                }
            )
        if punkte_entity:
            cards.append(
                {
                    "type": "gauge",
                    "entity": punkte_entity,
                    "name": f"{cfg['name']} - heute",
                    "min": 0,
                    "max": max(data.task_count(idx), 1),
                    "severity": {"red": 0, "yellow": 1, "green": data.task_count(idx)},
                }
            )

    wochenpunkte_entity = _entity_id(hass, "sensor", f"{entry.entry_id}_wochenpunkte")
    punktekonto_entity = _entity_id(hass, "sensor", f"{entry.entry_id}_punktekonto")

    weekly_target = max(
        sum(data.task_count(i) * len(data.weekdays(i)) for i in range(len(data.routines_config)))
        + (
            data.bonus_points() * sum(len(data.weekdays(i)) for i in range(len(data.routines_config)))
            if data.bonus_enabled()
            else 0
        ),
        1,
    )

    bottom_row: list[dict[str, Any]] = []
    if wochenpunkte_entity:
        bottom_row.append(
            {
                "type": "gauge",
                "entity": wochenpunkte_entity,
                "name": "Wochenpunkte",
                "min": 0,
                "max": weekly_target,
                "severity": {"red": 0, "yellow": weekly_target // 2, "green": weekly_target},
            }
        )
    if punktekonto_entity:
        bottom_row.append(
            {
                "type": "tile",
                "entity": punktekonto_entity,
                "name": "Punktekonto (Sparkonto)",
            }
        )
    if bottom_row:
        cards.append({"type": "horizontal-stack", "cards": bottom_row})

    return {
        "title": f"{data.kind_name()} Routinen",
        "views": [
            {
                "title": "Heute",
                "path": "heute",
                "cards": cards,
            }
        ],
    }


async def async_setup_dashboard(hass: HomeAssistant, entry: ConfigEntry, data) -> None:
    """Legt (oder aktualisiert) das Dashboard des Kindes an. Best effort."""
    lovelace_config = _build_lovelace_config(hass, entry, data)

    try:
        await _async_register_or_update(hass, entry, data, lovelace_config)
        return
    except Exception:  # noqa: BLE001 - interne API, absichtlich sehr defensiv
        _LOGGER.warning(
            "Automatische Dashboard-Registrierung fuer '%s' nicht moeglich - "
            "erzeuge stattdessen eine YAML-Datei zum manuellen Hinzufuegen",
            data.kind_name(),
            exc_info=True,
        )

    await _async_write_fallback_yaml(hass, data, lovelace_config)


async def _async_register_or_update(
    hass: HomeAssistant, entry: ConfigEntry, data, lovelace_config: dict[str, Any]
) -> None:
    from homeassistant.components import frontend
    from homeassistant.components.lovelace import dashboard as ll_dashboard
    from homeassistant.components.lovelace.const import (
        CONF_ICON,
        CONF_REQUIRE_ADMIN,
        CONF_SHOW_IN_SIDEBAR,
        CONF_TITLE,
        CONF_URL_PATH,
        LOVELACE_DATA,
    )
    from homeassistant.helpers.storage import Store

    if LOVELACE_DATA not in hass.data:
        raise RuntimeError("lovelace-Komponente ist nicht geladen")

    lovelace_data = hass.data[LOVELACE_DATA]

    # Bereits frueher angelegt (z. B. bei einem Reload) -> nur Inhalt updaten.
    if data.dashboard_url_path and frontend.async_panel_exists(hass, data.dashboard_url_path):
        existing = lovelace_data.dashboards.get(data.dashboard_url_path)
        if existing is not None:
            await existing.async_save(lovelace_config)
            return

    icon = "mdi:star-circle"
    title = f"{data.kind_name()} Routinen"
    base_slug = slugify(data.kind_name())
    url_path = f"kinder-routinen-{base_slug}"
    if frontend.async_panel_exists(hass, url_path):
        suffix = 2
        while frontend.async_panel_exists(hass, f"{url_path}-{suffix}"):
            suffix += 1
        url_path = f"{url_path}-{suffix}"

    dashboards_store: Store = Store(
        hass, ll_dashboard.DASHBOARDS_STORAGE_VERSION, ll_dashboard.DASHBOARDS_STORAGE_KEY
    )
    raw = await dashboards_store.async_load() or {"items": []}
    existing_ids = {item["id"] for item in raw.get("items", [])}
    item_id = base_slug
    suffix = 2
    while item_id in existing_ids:
        item_id = f"{base_slug}_{suffix}"
        suffix += 1

    item = {
        "id": item_id,
        CONF_URL_PATH: url_path,
        CONF_REQUIRE_ADMIN: False,
        CONF_ICON: icon,
        CONF_TITLE: title,
        CONF_SHOW_IN_SIDEBAR: True,
        "mode": "storage",
    }
    raw.setdefault("items", []).append(item)
    await dashboards_store.async_save(raw)

    storage_dashboard = ll_dashboard.LovelaceStorage(hass, item)
    await storage_dashboard.async_save(lovelace_config)
    lovelace_data.dashboards[url_path] = storage_dashboard

    frontend.async_register_built_in_panel(
        hass,
        "lovelace",
        sidebar_title=title,
        sidebar_icon=icon,
        frontend_url_path=url_path,
        config={"mode": "storage"},
        require_admin=False,
        show_in_sidebar=True,
    )

    data.dashboard_url_path = url_path
    data.dashboard_item_id = item_id
    await data.async_save()
    _LOGGER.info("Dashboard '%s' automatisch unter /%s angelegt", title, url_path)


async def async_remove_dashboard(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Best-effort-Aufraeumen beim endgueltigen Entfernen des Eintrags.

    WICHTIG: async_unload_entry laeuft VOR async_remove_entry und entfernt
    dabei bereits das In-Memory-KinderRoutinenData-Objekt aus hass.data - an
    dieser Stelle also nicht mehr verfuegbar. Die Dashboard-Infos werden
    deshalb direkt aus dem eigenen, weiterhin vorhandenen Store gelesen statt
    aus hass.data[DOMAIN].
    """
    from homeassistant.helpers.storage import Store as _Store
    from .const import STORAGE_VERSION as _STORAGE_VERSION

    own_store = _Store(hass, _STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}")
    stored = await own_store.async_load()
    url_path = stored.get("dashboard_url_path") if stored else None
    item_id = stored.get("dashboard_item_id") if stored else None

    if url_path:
        try:
            from homeassistant.components import frontend
            from homeassistant.components.lovelace import dashboard as ll_dashboard
            from homeassistant.components.lovelace.const import LOVELACE_DATA
            from homeassistant.helpers.storage import Store

            frontend.async_remove_panel(hass, url_path, warn_if_unknown=False)
            if LOVELACE_DATA in hass.data:
                storage_dashboard = hass.data[LOVELACE_DATA].dashboards.pop(url_path, None)
                if storage_dashboard is not None:
                    await storage_dashboard.async_delete()

            dashboards_store: Store = Store(
                hass, ll_dashboard.DASHBOARDS_STORAGE_VERSION, ll_dashboard.DASHBOARDS_STORAGE_KEY
            )
            raw = await dashboards_store.async_load()
            if raw:
                raw["items"] = [i for i in raw.get("items", []) if i.get("id") != item_id]
                await dashboards_store.async_save(raw)
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "Konnte automatisch angelegtes Dashboard nicht sauber entfernen", exc_info=True
            )

    await own_store.async_remove()


async def _async_write_fallback_yaml(hass: HomeAssistant, data, lovelace_config: dict[str, Any]) -> None:
    from homeassistant.components.persistent_notification import async_create
    from homeassistant.util.yaml import dump

    filename = f"kinder_routinen_{slugify(data.kind_name())}_dashboard.yaml"
    path = hass.config.path(filename)
    yaml_text = dump(lovelace_config["views"][0])

    def _write() -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(yaml_text)

    await hass.async_add_executor_job(_write)

    async_create(
        hass,
        (
            f"Das Dashboard fuer **{data.kind_name()}** konnte nicht automatisch in der "
            "Seitenleiste angelegt werden (das nutzt eine interne HA-API, die sich "
            "zwischen Versionen aendern kann).\n\n"
            f"Fertige Dashboard-YAML liegt unter `{filename}` im Konfigurationsverzeichnis. "
            "So fuegst du sie manuell hinzu: **Einstellungen → Dashboards → "
            "Dashboard hinzufuegen → Neues Dashboard aus YAML → Inhalt der Datei "
            "einfuegen.**"
        ),
        title="Kinder-Routinen: Dashboard manuell hinzufuegen",
        notification_id=f"kinder_routinen_dashboard_{slugify(data.kind_name())}",
    )
