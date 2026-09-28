"""Config flow (Setup-Assistent) fuer Kinder-Routinen Punktesystem.

v0.2: Ein-Klick-Assistent, der ALLES abfragt und selbst anlegt - keine
manuellen Helper/To-Do-Listen mehr noetig:

1. Schritt "user": Name des Kindes + Anzahl Routinen (1-6)
2. Schritt "routine" (wiederholt sich pro Routine): Name, Frist-Uhrzeit,
   Wochentage, die einzelnen Aufgaben (Freitext, eine pro Zeile) - daraus
   wird beim Setup automatisch eine eigene To-Do-Liste erzeugt.
3. Schritt "punkte": ein berechneter Vorschlag fuer ein "schoenes"
   Punktesystem (rundes Wochenziel), Bonuspunkte als Opt-in, Notify-Ziel.

Alle Routinen eines Kindes teilen sich EIN Wochenpunktekonto und EIN
Sparkonto (siehe README-Entscheidung "gemeinsames Konto pro Kind").
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    CONF_BONUS_ENABLED,
    CONF_BONUS_POINTS,
    CONF_KIND_NAME,
    CONF_NOTIFY_TARGET,
    CONF_ROUTINE_COUNT,
    CONF_ROUTINES,
    MAX_ROUTINES,
    NICE_WEEKLY_TARGETS,
    ROUTINE_DEADLINE,
    ROUTINE_NAME,
    ROUTINE_TASKS,
    ROUTINE_WEEKDAYS,
    WEEKDAY_OPTIONS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _parse_tasks(raw: str) -> list[str]:
    """Wandelt mehrzeiligen Freitext in eine bereinigte Aufgabenliste um."""
    return [line.strip() for line in raw.splitlines() if line.strip()]


def suggest_points(routines: list[dict]) -> tuple[int, int, int]:
    """Berechnet Basis-Wochenpunkte, ein 'schoenes' Wochenziel und einen
    Bonusvorschlag, der die Differenz zwischen Basis und Ziel gleichmaessig
    auf alle Routinen-Tage verteilt.
    """
    base = sum(
        len(r[ROUTINE_TASKS]) * len(r[ROUTINE_WEEKDAYS]) for r in routines
    )
    bonus_slots = sum(len(r[ROUTINE_WEEKDAYS]) for r in routines)

    target = next((t for t in NICE_WEEKLY_TARGETS if t >= base), None)
    if target is None:
        target = ((base // 50) + 1) * 50
    if target <= base:
        target = base + max(bonus_slots, 1)

    bonus_points = max(1, round((target - base) / bonus_slots)) if bonus_slots else 0
    return base, target, bonus_points


class KinderRoutinenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Setup-Assistent fuer das Kinder-Routinen Punktesystem."""

    VERSION = 2

    def __init__(self) -> None:
        self._kind_name: str | None = None
        self._routine_count: int = 1
        self._routine_index: int = 0
        self._routines: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._kind_name = user_input[CONF_KIND_NAME]
            self._routine_count = int(user_input[CONF_ROUTINE_COUNT])
            self._routines = []
            self._routine_index = 0
            await self.async_set_unique_id(self._kind_name.strip().lower())
            self._abort_if_unique_id_configured()
            return await self.async_step_routine()

        schema = vol.Schema(
            {
                vol.Required(CONF_KIND_NAME): str,
                vol.Required(CONF_ROUTINE_COUNT, default=2): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=MAX_ROUTINES, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_routine(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            tasks = _parse_tasks(user_input[ROUTINE_TASKS])
            if not tasks:
                errors["base"] = "no_tasks"
            elif not user_input[ROUTINE_WEEKDAYS]:
                errors["base"] = "no_weekdays"
            else:
                self._routines.append(
                    {
                        ROUTINE_NAME: user_input[ROUTINE_NAME],
                        ROUTINE_DEADLINE: user_input[ROUTINE_DEADLINE],
                        ROUTINE_WEEKDAYS: user_input[ROUTINE_WEEKDAYS],
                        ROUTINE_TASKS: tasks,
                    }
                )
                self._routine_index += 1
                if self._routine_index >= self._routine_count:
                    return await self.async_step_punkte()
                return await self.async_step_routine()

        default_name = (
            "Morgen"
            if self._routine_index == 0
            else "Mittag"
            if self._routine_index == 1
            else f"Routine {self._routine_index + 1}"
        )
        schema = vol.Schema(
            {
                vol.Required(ROUTINE_NAME, default=default_name): str,
                vol.Required(ROUTINE_DEADLINE, default="08:00:00"): selector.TimeSelector(),
                vol.Required(
                    ROUTINE_WEEKDAYS, default=WEEKDAY_OPTIONS[:5]
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=WEEKDAY_OPTIONS,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="weekday",
                    )
                ),
                vol.Required(ROUTINE_TASKS): selector.TextSelector(
                    selector.TextSelectorConfig(
                        multiline=True, type=selector.TextSelectorType.TEXT
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="routine",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "index": str(self._routine_index + 1),
                "count": str(self._routine_count),
                "kind_name": self._kind_name or "",
            },
        )

    async def async_step_punkte(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        base, target, bonus_suggestion = suggest_points(self._routines)

        if user_input is not None:
            bonus_enabled = user_input[CONF_BONUS_ENABLED]
            data = {
                CONF_KIND_NAME: self._kind_name,
                CONF_ROUTINES: self._routines,
                CONF_BONUS_ENABLED: bonus_enabled,
                CONF_BONUS_POINTS: int(user_input[CONF_BONUS_POINTS]) if bonus_enabled else 0,
                CONF_NOTIFY_TARGET: user_input[CONF_NOTIFY_TARGET],
            }
            return self.async_create_entry(title=self._kind_name, data=data)

        schema = vol.Schema(
            {
                vol.Required(CONF_BONUS_ENABLED, default=True): selector.BooleanSelector(),
                vol.Required(
                    CONF_BONUS_POINTS, default=bonus_suggestion
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=50, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_NOTIFY_TARGET, default="notify.notify"): str,
            }
        )
        return self.async_show_form(
            step_id="punkte",
            data_schema=schema,
            description_placeholders={
                "base": str(base),
                "target": str(target),
                "bonus_suggestion": str(bonus_suggestion),
            },
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return KinderRoutinenOptionsFlow(config_entry)


class KinderRoutinenOptionsFlow(config_entries.OptionsFlow):
    """Nachtraegliches Anpassen von Bonus und Notify-Ziel.

    Das Hinzufuegen/Entfernen einzelner Routinen nach dem Setup ist fuer
    eine spaetere Version geplant (siehe README-Roadmap) - aktuell dafuer:
    Eintrag entfernen und den Assistenten erneut durchlaufen.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._entry.data
        base, target, bonus_suggestion = suggest_points(current.get(CONF_ROUTINES, []))
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BONUS_ENABLED,
                    default=self._entry.options.get(
                        CONF_BONUS_ENABLED, current.get(CONF_BONUS_ENABLED, True)
                    ),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_BONUS_POINTS,
                    default=self._entry.options.get(
                        CONF_BONUS_POINTS, current.get(CONF_BONUS_POINTS, bonus_suggestion)
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=50, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_NOTIFY_TARGET,
                    default=self._entry.options.get(
                        CONF_NOTIFY_TARGET, current.get(CONF_NOTIFY_TARGET, "notify.notify")
                    ),
                ): str,
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={
                "base": str(base),
                "target": str(target),
            },
        )
