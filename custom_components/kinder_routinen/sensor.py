"""Sensor-Plattform fuer Kinder-Routinen Punktesystem.

v0.2: Pro Routine ein "Punkte heute"/"Tagesmax"-Sensorpaar, plus zwei
Sensoren auf Kind-Ebene fuer das gemeinsame Wochenpunkte-/Punktekonto.

v1.0: Zusaetzlich pro Routine ein "Aktuelles Bild"-Sensor, der ueber sein
entity_picture-Attribut das zur zuletzt abgehakten Aufgabe passende Bild
zeigt (oder Grundbild/Alles-erledigt) - siehe
KinderRoutinenData.current_image_info in __init__.py. Wird vom
automatisch generierten Dashboard (dashboard.py) als picture-entity-Karte
eingebunden, wenn fuer die Routine mindestens ein Bild hinterlegt ist.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KinderRoutinenData
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data: KinderRoutinenData = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        WochenpunkteSensor(entry, data),
        PunktekontoSensor(entry, data),
    ]
    for idx in range(data.routine_count()):
        entities.append(RoutinePunkteHeuteSensor(entry, data, idx))
        entities.append(RoutineTagesmaxSensor(entry, data, idx))
        entities.append(RoutineAktuellesBildSensor(entry, data, idx))
    async_add_entities(entities)


class _DeviceSensorMixin:
    """Gemeinsames Grundgeruest (Device-Zuordnung, Listener-Anbindung)."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, data: KinderRoutinenData) -> None:
        self._entry = entry
        self._data = data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=data.kind_name(),
            manufacturer="Kinder-Routinen Punktesystem",
        )

    async def async_added_to_hass(self) -> None:
        self._data.add_listener(self.async_write_ha_state)


class _BaseSensor(_DeviceSensorMixin, SensorEntity):
    """Fuer numerische Zaehler-Sensoren (Punkte, Tagesmax, ...)."""

    _attr_state_class = SensorStateClass.MEASUREMENT


class RoutinePunkteHeuteSensor(_BaseSensor):
    _attr_icon = "mdi:star"

    def __init__(self, entry: ConfigEntry, data: KinderRoutinenData, index: int) -> None:
        super().__init__(entry, data)
        self._index = index
        self._attr_name = f"{data.routine_name(index)} - Punkte heute"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_punkte_heute_{self._index}"

    @property
    def native_value(self) -> int:
        return self._data.routine_state[self._index]["points_awarded"]


class RoutineTagesmaxSensor(_BaseSensor):
    _attr_icon = "mdi:star-outline"

    def __init__(self, entry: ConfigEntry, data: KinderRoutinenData, index: int) -> None:
        super().__init__(entry, data)
        self._index = index
        self._attr_name = f"{data.routine_name(index)} - Tagesmax"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_tagesmax_{self._index}"

    @property
    def native_value(self) -> int:
        return self._data.task_count(self._index)


class RoutineAktuellesBildSensor(_DeviceSensorMixin, SensorEntity):
    """v1.0: zeigt per entity_picture das zur aktuellen Routinen-Phase
    passende Bild - kein state_class, da kein numerischer Messwert."""

    _attr_icon = "mdi:image-outline"

    def __init__(self, entry: ConfigEntry, data: KinderRoutinenData, index: int) -> None:
        super().__init__(entry, data)
        self._index = index
        self._attr_name = f"{data.routine_name(index)} - Aktuelles Bild"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_bild_{self._index}"

    @property
    def native_value(self) -> str:
        _, label = self._data.current_image_info(self._index)
        return label

    @property
    def entity_picture(self) -> str | None:
        image, _ = self._data.current_image_info(self._index)
        return image


class WochenpunkteSensor(_BaseSensor):
    _attr_name = "Wochenpunkte"
    _attr_icon = "mdi:calendar-week"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_wochenpunkte"

    @property
    def native_value(self) -> int:
        return self._data.wochenpunkte


class PunktekontoSensor(_BaseSensor):
    _attr_name = "Punktekonto"
    _attr_icon = "mdi:piggy-bank"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_punktekonto"

    @property
    def native_value(self) -> int:
        return self._data.punktekonto
