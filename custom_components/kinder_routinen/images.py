"""Bild-Upload-Hilfsfunktionen fuer Kinder-Routinen Punktesystem.

v1.0: Der Einrichtungsassistent und der Options-Flow lassen pro Aufgabe
(und optional pro Routine ein "Grundbild"/"Alles erledigt"-Bild) einen
Datei-Upload zu (HA-Bordmittel: selector.FileSelector, siehe config_flow.py
und options_flow.py). Diese Datei kapselt das dauerhafte Ablegen dieser
Bilder.

Hochgeladene Bilder werden nach config/www/<WWW_IMAGE_SUBDIR>/<kind_slug>/...
kopiert. Alles unterhalb von config/www wird von Home Assistant automatisch
unter /local/... ausgeliefert - es braucht dafuer keine eigene
Static-Path-Registrierung oder einen eigenen HTTP-View.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.core import HomeAssistant

from .const import WWW_IMAGE_SUBDIR

_LOGGER = logging.getLogger(__name__)


def _kind_dir(hass: HomeAssistant, kind_slug: str) -> Path:
    return Path(hass.config.path("www", WWW_IMAGE_SUBDIR, kind_slug))


async def async_store_uploaded_image(
    hass: HomeAssistant, kind_slug: str, file_id: str, dest_stem: str
) -> str | None:
    """Kopiert eine per FileSelector hochgeladene Datei dauerhaft nach
    config/www/<WWW_IMAGE_SUBDIR>/<kind_slug>/<dest_stem>.<ext> und gibt
    den lokal erreichbaren Web-Pfad (/local/...) zurueck, oder None, falls
    das Verarbeiten der hochgeladenen Datei fehlschlaegt (z. B. weil sie
    zwischenzeitlich schon verworfen wurde).
    """

    def _copy() -> str | None:
        try:
            with process_uploaded_file(hass, file_id) as src_path:
                target_dir = _kind_dir(hass, kind_slug)
                target_dir.mkdir(parents=True, exist_ok=True)
                suffix = src_path.suffix.lower() or ".jpg"
                dest = target_dir / f"{dest_stem}{suffix}"
                shutil.copy(src_path, dest)
                return f"/local/{WWW_IMAGE_SUBDIR}/{kind_slug}/{dest_stem}{suffix}"
        except (ValueError, OSError):
            _LOGGER.warning("Konnte hochgeladenes Bild nicht verarbeiten", exc_info=True)
            return None

    return await hass.async_add_executor_job(_copy)


async def async_delete_image(hass: HomeAssistant, web_path: str | None) -> None:
    """Loescht eine zuvor gespeicherte Bilddatei (best effort, kein Fehler
    falls sie schon weg ist)."""
    if not web_path or not web_path.startswith(f"/local/{WWW_IMAGE_SUBDIR}/"):
        return

    def _delete() -> None:
        rel = web_path[len("/local/") :]
        path = Path(hass.config.path("www", rel))
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
