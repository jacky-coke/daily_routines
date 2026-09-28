"""Config flow for Kinder-Routinen Punktesystem.

v0.1: eine Config-Entry pro Routine (z. B. eine fuer "Morgen", eine fuer
"Mittag") - analog zum bisherigen Blueprint-Modell (eine Instanz pro
Routine). Wochenpunkte/Punktekonto werden aktuell pro Entry getrennt
gefuehrt; das Zusammenfuehren mehrerer Routinen auf ein gemeinsames Konto
ist fuer eine spaetere Version geplant (siehe README-Roadmap).
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    CONF_BONUS_POINTS,
    CONF_DEADLINE,
    CONF_NAME,
    CONF_NOTIFY_TARGET,
    CONF_TASK_COUNT,
    CONF_TODO_ENTITY,
    CONF_WEEKDAYS,
    DOMAIN,
    WEEKDAY_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


async def _count_todo_items(hass: HomeAssistant, todo_entity: str) -> int:
    """Ermittelt automatisch die Gesamtzahl der Eintraege in der To-Do-Liste."""
    try:
        response = await hass.services.async_call(
            "todo",
            "get_items",
            {"entity_id": todo_entity},
            blocking=True,
            return_response=True,
        )
        items = response[todo_entity]["items"]
        return len(items)
    except Exception:  # noqa: BLE001 - best effort, notfalls manuell korrigierbar
        _LOGGER.warning(
            "Konnte Aufgabenanzahl fuer %s nicht automatisch ermitteln", todo_entity
        )
        return 0


class KinderRoutinenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config-Flow fuer das Kinder-Routinen Punktesystem."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            task_count = await _count_todo_items(self.hass, user_input[CONF_TODO_ENTITY])
            if task_count == 0:
                errors["base"] = "empty_todo_list"
            else:
                data = dict(user_input)
                data[CONF_TASK_COUNT] = task_count
                await self.async_set_unique_id(
                    f"{user_input[CONF_NAME]}_{user_input[CONF_TODO_ENTITY]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_NAME], data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_TODO_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="todo")
                ),
                vol.Required(CONF_DEADLINE): selector.TimeSelector(),
                vol.Required(
                    CONF_WEEKDAYS, default=WEEKDAY_OPTIONS[:5]
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=WEEKDAY_OPTIONS,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(CONF_BONUS_POINTS, default=3): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=50, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_NOTIFY_TARGET, default="notify.notify"): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return KinderRoutinenOptionsFlow(config_entry)


class KinderRoutinenOptionsFlow(config_entries.OptionsFlow):
    """Erlaubt das nachtraegliche Aendern von Frist/Wochentagen/Bonus/Notify-Ziel."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEADLINE, default=current.get(CONF_DEADLINE)
                ): selector.TimeSelector(),
                vol.Required(
                    CONF_WEEKDAYS, default=current.get(CONF_WEEKDAYS, WEEKDAY_OPTIONS[:5])
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=WEEKDAY_OPTIONS, multiple=True, mode=selector.SelectSelectorMode.LIST
                    )
                ),
                vol.Required(
                    CONF_BONUS_POINTS, default=current.get(CONF_BONUS_POINTS, 3)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=50, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_NOTIFY_TARGET, default=current.get(CONF_NOTIFY_TARGET, "notify.notify")
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
