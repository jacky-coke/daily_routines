"""Options-Flow (nachtraegliche Verwaltung) fuer Kinder-Routinen Punktesystem.

v1.0: Menuegefuehrte Verwaltung ueber Einstellungen -> Integration ->
Konfigurieren:

- "Einstellungen" - Bonuspunkte/Notify-Ziel (wie schon in v0.2).
- "Routine hinzufuegen" - derselbe Mini-Assistent wie beim Ersteinrichten
  (Name/Frist/Wochentage/Aufgaben + optionale Bilder je Aufgabe).
- "Aufgaben bearbeiten" - Aufgabenliste einer Routine als Text bearbeiten
  (eine Zeile = eine Aufgabe); Zeilen hinzufuegen/entfernen/umbenennen wird
  automatisch als Hinzufuegen/Entfernen/Umbenennen der jeweiligen
  To-Do-Eintraege erkannt (per difflib-Textvergleich, damit unveraenderte
  Aufgaben - inkl. ihres Status und Bilds - wirklich unveraendert bleiben).
- "Bild einer Aufgabe aendern" - eine bestehende Aufgabe auswaehlen und ein
  neues Bild hochladen.
- "Routineneinstellungen bearbeiten" - Name/Frist/Wochentage einer Routine
  sowie optional Grundbild/Alles-erledigt-Bild ersetzen.
- "Routine entfernen" - inkl. Aufraeumen ihrer Bilder und (wegen der aus
  Kompatibilitaetsgruenden positionsbasierten Entity-unique_ids) der dabei
  verwaisten obersten Entity-Positionen, siehe
  __init__.py:_async_cleanup_orphaned_entities.

Architektur-Hinweis: alle hier vorgenommenen Aenderungen werden direkt im
persistenten Store der Integration (KinderRoutinenData, siehe __init__.py)
vorgenommen und danach per hass.config_entries.async_reload() angewendet,
damit betroffene Entities (To-Do-Liste, Sensoren) neu entstehen bzw. den
neuen Stand zeigen. entry.data[CONF_ROUTINES] wird bei Hinzufuegen/Entfernen
einer ganzen Routine mitgepflegt (fuer Anzahl/Reihenfolge), ist fuer
bestehende Routinen aber nur noch der EINMALIGE Startzustand - siehe
Modul-Docstring von __init__.py.
"""
from __future__ import annotations

import difflib
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from . import KinderRoutinenData, _async_cleanup_orphaned_entities
from .config_flow import (
    _parse_tasks,
    bilder_tasks_list,
    build_bilder_schema,
    process_bilder_submission,
    suggest_points,
)
from .const import (
    CONF_BONUS_ENABLED,
    CONF_BONUS_POINTS,
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
    WEEKDAY_OPTIONS,
)
from .images import async_store_uploaded_image

_LOGGER = logging.getLogger(__name__)

FIELD_ROUTINE_INDEX = "routine_index"
FIELD_TASK_UID = "task_uid"
FIELD_BILD = "bild"
FIELD_GRUNDBILD_NEU = "bild_grundbild_neu"
FIELD_ERLEDIGT_NEU = "bild_alles_erledigt_neu"
FIELD_BESTAETIGEN = "bestaetigen"


class KinderRoutinenOptionsFlow(config_entries.OptionsFlow):
    """Nachtraegliches Anpassen von Bonus/Notify-Ziel sowie - ab v1.0 -
    Hinzufuegen/Entfernen/Bearbeiten von Routinen, Aufgaben und Bildern."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        self._target_index: int | None = None
        self._pending_new_routine: dict[str, Any] | None = None

    def _data(self) -> KinderRoutinenData:
        return self.hass.data[DOMAIN][self._entry.entry_id]

    def _finish(self) -> config_entries.ConfigFlowResult:
        """Beendet den Options-Flow ohne die entry.options zu aendern."""
        return self.async_create_entry(title="", data=dict(self._entry.options))

    def _routine_select_schema(self) -> vol.Schema:
        data = self._data()
        options = [
            selector.SelectOptionDict(value=str(i), label=data.routine_name(i))
            for i in range(data.routine_count())
        ]
        return vol.Schema(
            {
                vol.Required(FIELD_ROUTINE_INDEX): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )

    # -- Menue ---------------------------------------------------------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "einstellungen",
                "routine_hinzufuegen",
                "routine_aufgaben_bearbeiten",
                "routine_aufgabe_bild",
                "routine_einstellungen_bearbeiten",
                "routine_entfernen",
            ],
        )

    # -- Bonus/Notify (wie v0.2) -----------------------------------------

    async def async_step_einstellungen(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self._data()
        base = sum(
            data.task_count(i) * len(data.weekdays(i)) for i in range(data.routine_count())
        )
        _, target, bonus_suggestion = suggest_points(
            [
                {ROUTINE_TASKS: [None] * data.task_count(i), ROUTINE_WEEKDAYS: data.weekdays(i)}
                for i in range(data.routine_count())
            ]
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_BONUS_ENABLED, default=data.bonus_enabled()
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_BONUS_POINTS, default=data.bonus_points() or bonus_suggestion
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=50, mode=selector.NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_NOTIFY_TARGET, default=data.notify_target()): str,
            }
        )
        return self.async_show_form(
            step_id="einstellungen",
            data_schema=schema,
            description_placeholders={"base": str(base), "target": str(target)},
        )

    # -- Routine hinzufuegen ---------------------------------------------

    async def async_step_routine_hinzufuegen(
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
                self._pending_new_routine = {
                    ROUTINE_NAME: user_input[ROUTINE_NAME],
                    ROUTINE_DEADLINE: user_input[ROUTINE_DEADLINE],
                    ROUTINE_WEEKDAYS: user_input[ROUTINE_WEEKDAYS],
                    ROUTINE_TASKS: tasks,
                }
                return await self.async_step_routine_hinzufuegen_bilder()

        schema = vol.Schema(
            {
                vol.Required(
                    ROUTINE_NAME, default=f"Routine {self._data().routine_count() + 1}"
                ): str,
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
        return self.async_show_form(step_id="routine_hinzufuegen", data_schema=schema, errors=errors)

    async def async_step_routine_hinzufuegen_bilder(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        assert self._pending_new_routine is not None
        tasks = self._pending_new_routine[ROUTINE_TASKS]

        if user_input is not None:
            data = self._data()
            kind_slug = data.kind_slug
            new_index = data.routine_count()
            task_images, base_image, done_image = await process_bilder_submission(
                self.hass, kind_slug, f"routine{new_index}", tasks, user_input
            )
            items = [
                {
                    "uid": f"{new_index}_{j}",
                    "summary": t,
                    "status": "needs_action",
                    "image": task_images[j],
                    "completed_at": None,
                }
                for j, t in enumerate(tasks)
            ]
            await data.async_append_routine(
                {
                    "name": self._pending_new_routine[ROUTINE_NAME],
                    "deadline": self._pending_new_routine[ROUTINE_DEADLINE],
                    "weekdays": self._pending_new_routine[ROUTINE_WEEKDAYS],
                    "base_image": base_image,
                    "done_image": done_image,
                    "completed": 0,
                    "points_awarded": 0,
                    "items": items,
                }
            )
            new_cfg_entry = {
                ROUTINE_NAME: self._pending_new_routine[ROUTINE_NAME],
                ROUTINE_DEADLINE: self._pending_new_routine[ROUTINE_DEADLINE],
                ROUTINE_WEEKDAYS: self._pending_new_routine[ROUTINE_WEEKDAYS],
                ROUTINE_TASKS: tasks,
                ROUTINE_TASK_IMAGES: task_images,
                ROUTINE_BASE_IMAGE: base_image,
                ROUTINE_DONE_IMAGE: done_image,
            }
            new_routines = list(self._entry.data[CONF_ROUTINES]) + [new_cfg_entry]
            self.hass.config_entries.async_update_entry(
                self._entry, data={**self._entry.data, CONF_ROUTINES: new_routines}
            )
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            self._pending_new_routine = None
            return self._finish()

        return self.async_show_form(
            step_id="routine_hinzufuegen_bilder",
            data_schema=build_bilder_schema(tasks),
            description_placeholders={"tasks_list": bilder_tasks_list(tasks)},
        )

    # -- Aufgaben bearbeiten (Textliste, per Diff angewendet) ------------

    async def async_step_routine_aufgaben_bearbeiten(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._data().routine_count() == 0:
            return self.async_abort(reason="no_routines")
        if user_input is not None:
            self._target_index = int(user_input[FIELD_ROUTINE_INDEX])
            return await self.async_step_aufgaben_text()
        return self.async_show_form(
            step_id="routine_aufgaben_bearbeiten", data_schema=self._routine_select_schema()
        )

    async def async_step_aufgaben_text(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        data = self._data()
        idx = self._target_index
        assert idx is not None
        current_tasks = [i["summary"] for i in data.items(idx)]
        errors: dict[str, str] = {}

        if user_input is not None:
            new_tasks = _parse_tasks(user_input[ROUTINE_TASKS])
            if not new_tasks:
                errors["base"] = "no_tasks"
            else:
                await self._apply_task_diff(data, idx, current_tasks, new_tasks)
                await self.hass.config_entries.async_reload(self._entry.entry_id)
                return self._finish()

        schema = vol.Schema(
            {
                vol.Required(
                    ROUTINE_TASKS, default="\n".join(current_tasks)
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        multiline=True, type=selector.TextSelectorType.TEXT
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="aufgaben_text",
            data_schema=schema,
            errors=errors,
            description_placeholders={"routine_name": data.routine_name(idx)},
        )

    async def _apply_task_diff(
        self, data: KinderRoutinenData, index: int, old_texts: list[str], new_texts: list[str]
    ) -> None:
        """Vergleicht alte/neue Aufgabenliste (Text-Diff) und wendet nur
        die tatsaechlichen Aenderungen an, damit unveraenderte Aufgaben
        ihren Status/ihr Bild behalten."""
        items = data.items(index)
        matcher = difflib.SequenceMatcher(a=old_texts, b=new_texts, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            if tag == "replace":
                overlap = min(i2 - i1, j2 - j1)
                for k in range(overlap):
                    await data.async_rename_item(index, items[i1 + k]["uid"], new_texts[j1 + k])
                if (i2 - i1) > overlap:
                    uids = [items[i1 + overlap + k]["uid"] for k in range(i2 - i1 - overlap)]
                    await data.async_delete_items(index, uids)
                if (j2 - j1) > overlap:
                    for k in range(j2 - j1 - overlap):
                        await data.async_add_item(index, new_texts[j1 + overlap + k])
            elif tag == "delete":
                uids = [items[k]["uid"] for k in range(i1, i2)]
                await data.async_delete_items(index, uids)
            elif tag == "insert":
                for k in range(j1, j2):
                    await data.async_add_item(index, new_texts[k])

    # -- Bild einer einzelnen Aufgabe aendern ----------------------------

    async def async_step_routine_aufgabe_bild(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._data().routine_count() == 0:
            return self.async_abort(reason="no_routines")
        if user_input is not None:
            self._target_index = int(user_input[FIELD_ROUTINE_INDEX])
            return await self.async_step_aufgabe_bild_wahl()
        return self.async_show_form(
            step_id="routine_aufgabe_bild", data_schema=self._routine_select_schema()
        )

    async def async_step_aufgabe_bild_wahl(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        data = self._data()
        idx = self._target_index
        assert idx is not None
        items = data.items(idx)

        if user_input is not None:
            uid = user_input[FIELD_TASK_UID]
            image = await async_store_uploaded_image(
                self.hass, data.kind_slug, user_input[FIELD_BILD], f"routine{idx}_aufgabe_{uid}"
            )
            if image:
                await data.async_set_item_image(idx, uid, image)
                await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self._finish()

        task_options = [
            selector.SelectOptionDict(value=i["uid"], label=i["summary"]) for i in items
        ]
        schema = vol.Schema(
            {
                vol.Required(FIELD_TASK_UID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=task_options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
                vol.Required(FIELD_BILD): selector.FileSelector(
                    selector.FileSelectorConfig(accept="image/*")
                ),
            }
        )
        return self.async_show_form(
            step_id="aufgabe_bild_wahl",
            data_schema=schema,
            description_placeholders={"routine_name": data.routine_name(idx)},
        )

    # -- Routineneinstellungen (Name/Frist/Wochentage/Grundbilder) -------

    async def async_step_routine_einstellungen_bearbeiten(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._data().routine_count() == 0:
            return self.async_abort(reason="no_routines")
        if user_input is not None:
            self._target_index = int(user_input[FIELD_ROUTINE_INDEX])
            return await self.async_step_routine_einstellungen_form()
        return self.async_show_form(
            step_id="routine_einstellungen_bearbeiten", data_schema=self._routine_select_schema()
        )

    async def async_step_routine_einstellungen_form(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        data = self._data()
        idx = self._target_index
        assert idx is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            weekdays = user_input[ROUTINE_WEEKDAYS]
            if not weekdays:
                errors["base"] = "no_weekdays"
            else:
                await data.async_update_routine_meta(
                    idx,
                    name=user_input[ROUTINE_NAME],
                    deadline=user_input[ROUTINE_DEADLINE],
                    weekdays=weekdays,
                )
                kind_slug = data.kind_slug
                if user_input.get(FIELD_GRUNDBILD_NEU):
                    image = await async_store_uploaded_image(
                        self.hass, kind_slug, user_input[FIELD_GRUNDBILD_NEU], f"routine{idx}_grundbild"
                    )
                    await data.async_set_routine_image(idx, "base_image", image)
                if user_input.get(FIELD_ERLEDIGT_NEU):
                    image = await async_store_uploaded_image(
                        self.hass, kind_slug, user_input[FIELD_ERLEDIGT_NEU], f"routine{idx}_erledigt"
                    )
                    await data.async_set_routine_image(idx, "done_image", image)
                await self.hass.config_entries.async_reload(self._entry.entry_id)
                return self._finish()

        schema = vol.Schema(
            {
                vol.Required(ROUTINE_NAME, default=data.routine_name(idx)): str,
                vol.Required(
                    ROUTINE_DEADLINE, default=data.deadline_str(idx)
                ): selector.TimeSelector(),
                vol.Required(
                    ROUTINE_WEEKDAYS, default=data.weekdays(idx)
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=WEEKDAY_OPTIONS,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key="weekday",
                    )
                ),
                vol.Optional(FIELD_GRUNDBILD_NEU): selector.FileSelector(
                    selector.FileSelectorConfig(accept="image/*")
                ),
                vol.Optional(FIELD_ERLEDIGT_NEU): selector.FileSelector(
                    selector.FileSelectorConfig(accept="image/*")
                ),
            }
        )
        return self.async_show_form(
            step_id="routine_einstellungen_form",
            data_schema=schema,
            errors=errors,
            description_placeholders={"routine_name": data.routine_name(idx)},
        )

    # -- Routine entfernen -------------------------------------------------

    async def async_step_routine_entfernen(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._data().routine_count() == 0:
            return self.async_abort(reason="no_routines")
        if user_input is not None:
            self._target_index = int(user_input[FIELD_ROUTINE_INDEX])
            return await self.async_step_routine_entfernen_bestaetigen()
        return self.async_show_form(
            step_id="routine_entfernen", data_schema=self._routine_select_schema()
        )

    async def async_step_routine_entfernen_bestaetigen(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        data = self._data()
        idx = self._target_index
        assert idx is not None
        routine_name = data.routine_name(idx)

        if user_input is not None:
            if user_input[FIELD_BESTAETIGEN]:
                await data.async_pop_routine(idx)
                new_routines = list(self._entry.data[CONF_ROUTINES])
                if idx < len(new_routines):
                    new_routines.pop(idx)
                self.hass.config_entries.async_update_entry(
                    self._entry, data={**self._entry.data, CONF_ROUTINES: new_routines}
                )
                await _async_cleanup_orphaned_entities(self.hass, self._entry, data.routine_count())
                await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self._finish()

        schema = vol.Schema({vol.Required(FIELD_BESTAETIGEN, default=False): selector.BooleanSelector()})
        return self.async_show_form(
            step_id="routine_entfernen_bestaetigen",
            data_schema=schema,
            description_placeholders={"routine_name": routine_name},
        )
