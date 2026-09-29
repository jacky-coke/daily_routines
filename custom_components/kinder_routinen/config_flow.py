"""Config flow (Setup-Assistent) fuer Kinder-Routinen Punktesystem.

v0.2: Ein-Klick-Assistent, der ALLES abfragt und selbst anlegt - keine
manuellen Helper/To-Do-Listen mehr noetig:

1. Schritt "user": Name des Kindes + Anzahl Routinen (1-6)
2. Schritt "routine" (wiederholt sich pro Routine): Name, Frist-Uhrzeit,
   Wochentage, die einzelnen Aufgaben (Freitext, eine pro Zeile) - daraus
   wird beim Setup automatisch eine eigene To-Do-Liste erzeugt.
3. Schritt "routine_bilder" (wiederholt sich pro Routine): optional pro
   Aufgabe ein Bild hochladen (zeigt beim Abhaken auf dem Dashboard), plus
   optional ein "Grundbild" (vor Routinenstart) und ein "Alles
   erledigt"-Bild.
4. Schritt "punkte": ein berechneter Vorschlag fuer ein "schoenes"
   Punktesystem (rundes Wochenziel), Bonuspunkte als Opt-in, Notify-Ziel.

Alle Routinen eines Kindes teilen sich EIN Wochenpunktekonto und EIN
Sparkonto (siehe README-Entscheidung "gemeinsames Konto pro Kind").

v1.0: der Options-Flow (siehe options_flow.py) erlaubt das nachtraegliche
Hinzufuegen/Entfernen/Bearbeiten von Routinen, Aufgaben und deren Bildern,
ueber genau denselben Bild-Upload-Mechanismus wie hier (siehe
_build_bilder_schema/_process_bilder_submission unten, von options_flow.py
wiederverwendet).
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_BONUS_ENABLED,
    CONF_BONUS_POINTS,
    CONF_KIND_NAME,
    CONF_NOTIFY_TARGET,
    CONF_ROUTINE_COUNT,
    CONF_ROUTINES,
    DOMAIN,
    MAX_ROUTINES,
    NICE_WEEKLY_TARGETS,
    ROUTINE_BASE_IMAGE,
    ROUTINE_DEADLINE,
    ROUTINE_DONE_IMAGE,
    ROUTINE_NAME,
    ROUTINE_TASK_IMAGES,
    ROUTINE_TASKS,
    ROUTINE_WEEKDAYS,
    WEEKDAY_OPTIONS,
)
from .images import async_store_uploaded_image

_LOGGER = logging.getLogger(__name__)

FIELD_GRUNDBILD = "bild_grundbild"
FIELD_ALLES_ERLEDIGT = "bild_alles_erledigt"


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


def _field_aufgabe(index: int) -> str:
    return f"bild_aufgabe_{index}"


def build_bilder_schema(tasks: list[str]) -> vol.Schema:
    """Baut die dynamische Upload-Schema (ein optionales Bild je Aufgabe,
    plus Grundbild/Alles-erledigt) - von config_flow und options_flow
    gemeinsam genutzt."""
    fields: dict[Any, Any] = {}
    file_selector = selector.FileSelector(selector.FileSelectorConfig(accept="image/*"))
    for j in range(len(tasks)):
        fields[vol.Optional(_field_aufgabe(j))] = file_selector
    fields[vol.Optional(FIELD_GRUNDBILD)] = file_selector
    fields[vol.Optional(FIELD_ALLES_ERLEDIGT)] = file_selector
    return vol.Schema(fields)


def bilder_tasks_list(tasks: list[str]) -> str:
    return "\n".join(f"{j + 1}. {t}" for j, t in enumerate(tasks))


async def process_bilder_submission(
    hass: HomeAssistant,
    kind_slug: str,
    dest_prefix: str,
    tasks: list[str],
    user_input: dict[str, Any],
) -> tuple[list[str | None], str | None, str | None]:
    """Verarbeitet die hochgeladenen Dateien aus einem Bilder-Schritt und
    gibt (task_images, base_image, done_image) mit den dauerhaften
    /local/...-Pfaden zurueck (None, wo nichts hochgeladen wurde)."""
    task_images: list[str | None] = []
    for j in range(len(tasks)):
        file_id = user_input.get(_field_aufgabe(j))
        if file_id:
            task_images.append(
                await async_store_uploaded_image(
                    hass, kind_slug, file_id, f"{dest_prefix}_aufgabe{j}"
                )
            )
        else:
            task_images.append(None)

    base_image = None
    if user_input.get(FIELD_GRUNDBILD):
        base_image = await async_store_uploaded_image(
            hass, kind_slug, user_input[FIELD_GRUNDBILD], f"{dest_prefix}_grundbild"
        )

    done_image = None
    if user_input.get(FIELD_ALLES_ERLEDIGT):
        done_image = await async_store_uploaded_image(
            hass, kind_slug, user_input[FIELD_ALLES_ERLEDIGT], f"{dest_prefix}_erledigt"
        )

    return task_images, base_image, done_image


class KinderRoutinenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Setup-Assistent fuer das Kinder-Routinen Punktesystem."""

    VERSION = 2

    def __init__(self) -> None:
        self._kind_name: str | None = None
        self._routine_count: int = 1
        self._routine_index: int = 0
        self._routines: list[dict[str, Any]] = []
        self._pending_routine: dict[str, Any] | None = None

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
                self._pending_routine = {
                    ROUTINE_NAME: user_input[ROUTINE_NAME],
                    ROUTINE_DEADLINE: user_input[ROUTINE_DEADLINE],
                    ROUTINE_WEEKDAYS: user_input[ROUTINE_WEEKDAYS],
                    ROUTINE_TASKS: tasks,
                }
                return await self.async_step_routine_bilder()

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

    async def async_step_routine_bilder(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        assert self._pending_routine is not None
        tasks = self._pending_routine[ROUTINE_TASKS]

        if user_input is not None:
            kind_slug = slugify(self._kind_name or "")
            task_images, base_image, done_image = await process_bilder_submission(
                self.hass,
                kind_slug,
                f"routine{self._routine_index}",
                tasks,
                user_input,
            )
            self._pending_routine[ROUTINE_TASK_IMAGES] = task_images
            self._pending_routine[ROUTINE_BASE_IMAGE] = base_image
            self._pending_routine[ROUTINE_DONE_IMAGE] = done_image
            self._routines.append(self._pending_routine)
            self._pending_routine = None
            self._routine_index += 1
            if self._routine_index >= self._routine_count:
                return await self.async_step_punkte()
            return await self.async_step_routine()

        return self.async_show_form(
            step_id="routine_bilder",
            data_schema=build_bilder_schema(tasks),
            description_placeholders={
                "index": str(self._routine_index + 1),
                "count": str(self._routine_count),
                "tasks_list": bilder_tasks_list(tasks),
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
        # Lazy-Import, um einen Zirkelbezug config_flow <-> options_flow zu
        # vermeiden (options_flow importiert Hilfsfunktionen von hier).
        from .options_flow import KinderRoutinenOptionsFlow

        return KinderRoutinenOptionsFlow(config_entry)
