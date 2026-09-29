"""Bild-Upload-Hilfsfunktionen fuer Kinder-Routinen Punktesystem.

v1.0: Der Einrichtungsassistent und der Options-Flow lassen pro Aufgabe
(und optional pro Routine ein "Grundbild"/"Alles erledigt"-Bild) einen
Datei-Upload zu (HA-Bordmittel: selector.FileSelector, siehe config_flow.py
und options_flow.py). Diese Datei kapselt das dauerhafte Ablegen dieser
Bilder.

Hochgeladene Bilder werden nach config/www/<WWW_IMAGE_SUBDIR>/<kind_slug>/...
kopiert und unter STATIC_URL_PATH ausgeliefert.

WICHTIG (live auf der Testinstanz gefunden, siehe const.py): Home
Assistants eingebauter /local-Pfad wird von der frontend-Komponente NUR
beim HA-Start registriert und auch nur dann, wenn config/www zu diesem
Zeitpunkt schon existiert. Unser Bilderordner entsteht aber typischerweise
erst beim ersten Bild-Upload - ueber /local ausgelieferte Bilder wuerden
also bis zum naechsten Neustart 404en. Diese Datei registriert deshalb
beim ersten Upload selbst und dynamisch einen eigenen, garantiert
kollisionsfreien statischen Pfad (STATIC_URL_PATH), unabhaengig vom
Ladezeitpunkt.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, STATIC_URL_PATH, WWW_IMAGE_SUBDIR

_LOGGER = logging.getLogger(__name__)

_STATIC_PATH_REGISTERED_KEY = f"{DOMAIN}_static_path_registered"


def _kind_dir(hass: HomeAssistant, kind_slug: str) -> Path:
    return Path(hass.config.path("www", WWW_IMAGE_SUBDIR, kind_slug))


def _base_dir(hass: HomeAssistant) -> Path:
    return Path(hass.config.path("www", WWW_IMAGE_SUBDIR))


async def _async_ensure_static_path(hass: HomeAssistant) -> None:
    """Registriert einmalig (pro HA-Lauf) den eigenen statischen Pfad fuer
    die hochgeladenen Bilder - siehe Modul-Docstring, warum das eingebaute
    /local hier nicht zuverlaessig funktioniert."""
    if hass.data.get(_STATIC_PATH_REGISTERED_KEY):
        return

    base_dir = _base_dir(hass)

    def _ensure_dir() -> None:
        base_dir.mkdir(parents=True, exist_ok=True)

    await hass.async_add_executor_job(_ensure_dir)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL_PATH, str(base_dir), True)]
    )
    hass.data[_STATIC_PATH_REGISTERED_KEY] = True


async def async_store_uploaded_image(
    hass: HomeAssistant, kind_slug: str, file_id: str, dest_stem: str
) -> str | None:
    """Kopiert eine per FileSelector hochgeladene Datei dauerhaft nach
    config/www/<WWW_IMAGE_SUBDIR>/<kind_slug>/<dest_stem>.<ext> und gibt
    den ueber STATIC_URL_PATH erreichbaren Web-Pfad zurueck, oder None,
    falls das Verarbeiten der hochgeladenen Datei fehlschlaegt (z. B. weil
    sie zwischenzeitlich schon verworfen wurde).
    """
    await _async_ensure_static_path(hass)

    def _copy() -> str | None:
        try:
            with process_uploaded_file(hass, file_id) as src_path:
                target_dir = _kind_dir(hass, kind_slug)
                target_dir.mkdir(parents=True, exist_ok=True)
                suffix = src_path.suffix.lower() or ".jpg"
                dest = target_dir / f"{dest_stem}{suffix}"
                shutil.copy(src_path, dest)
                return f"{STATIC_URL_PATH}/{kind_slug}/{dest_stem}{suffix}"
        except (ValueError, OSError):
            _LOGGER.warning("Konnte hochgeladenes Bild nicht verarbeiten", exc_info=True)
            return None

    return await hass.async_add_executor_job(_copy)


async def async_delete_image(hass: HomeAssistant, web_path: str | None) -> None:
    """Loescht eine zuvor gespeicherte Bilddatei (best effort, kein Fehler
    falls sie schon weg ist)."""
    if not web_path or not web_path.startswith(f"{STATIC_URL_PATH}/"):
        return

    def _delete() -> None:
        rel = web_path[len(STATIC_URL_PATH) + 1 :]
        path = _base_dir(hass) / rel
        try:
            path.unlink(missing_ok=True)
        except OSError:
            _LOGGER.debug("Konnte Bilddatei nicht loeschen: %s", path)

    await hass.async_add_executor_job(_delete)


async def async_delete_kind_images(hass: HomeAssistant, kind_slug: str) -> None:
    """Loescht den kompletten Bilderordner eines Kindes (best effort, z. B.
    beim endgueltigen Entfernen des Config-Entrys)."""

    def _delete() -> None:
        shutil.rmtree(_kind_dir(hass, kind_slug), ignore_errors=True)

    await hass.async_add_executor_job(_delete)
