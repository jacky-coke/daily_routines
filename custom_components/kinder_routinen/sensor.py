"""Sensor-Plattform fuer Kinder-Routinen Punktesystem."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KinderRoutinenData
from .const import CONF_TASK_COUNT, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data: KinderRoutinenData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PunkteHeuteSensor(entry, data),
            TagesmaxSensor(entry, data),
            WochenpunkteSensor(entry, data),
            PunktekontoSensor(entry, data),
        ]
    )


class _BaseSensor(SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, data: KinderRoutinenData) -> None:
        self._entry = entry
        self._data = data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Kinder-Routinen Punktesystem",
        )

    async def async_added_to_hass(self) -> None:
        self._data.add_listener(self.async_write_ha_state)


class PunkteHeuteSensor(_BaseSensor):
    _attr_name = "Punkte heute"
    _attr_icon = "mdi:star"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_punkte_heute"

    @property
    def native_value(self) -> int:
        return self._data.heute_erledigt


class TagesmaxSensor(_BaseSensor):
    _attr_name = "Tagesmax"
    _attr_icon = "mdi:star-outline"

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}_tagesmax"

    @property
    def native_value(self) -> int:
        return self._entry.data[CONF_TASK_COUNT]


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
