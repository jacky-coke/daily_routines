"""To-Do-Plattform fuer Kinder-Routinen Punktesystem.

v0.2: Jede Routine bekommt eine eigene, integrationseigene To-Do-Liste
(keine externe To-Do-Integration mehr noetig - der Einrichtungsassistent
erzeugt die Liste direkt aus den im Dialog eingegebenen Aufgaben).

Wichtig fuer die Punktevergabe: async_update_todo_item ruft die Punkte-
Logik direkt synchron auf. Ein HA-Neustart fuehrt NIE zu einem Aufruf
dieser Methode (nur echte Nutzerinteraktion tut das) - die in v0.1
gefundene "Neustart schreibt faelschlich Punkte gut"-Bugklasse ist damit
architektonisch ausgeschlossen.
"""
from __future__ import annotations

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
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
    async_add_entities(
        RoutineTodoListEntity(entry, data, idx)
        for idx in range(data.routine_count())
    )


class RoutineTodoListEntity(TodoListEntity):
    """Eine To-Do-Liste, deren Inhalt vollstaendig von der Integration
    selbst verwaltet wird (Store-persistiert ueber KinderRoutinenData)."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, entry: ConfigEntry, data: KinderRoutinenData, index: int) -> None:
        self._entry = entry
        self._data = data
        self._index = index
        self._attr_unique_id = f"{entry.entry_id}_todo_{index}"
        self._attr_name = data.routine_name(index)
        self._attr_icon = "mdi:checkbox-marked-circle-outline"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=data.kind_name(),
            manufacturer="Kinder-Routinen Punktesystem",
        )

    async def async_added_to_hass(self) -> None:
        self._data.add_listener(self.async_write_ha_state)

    @property
    def todo_items(self) -> list[TodoItem]:
        return [
            TodoItem(
                uid=raw["uid"],
                summary=raw["summary"],
                status=TodoItemStatus(raw["status"]),
            )
            for raw in self._data.items(self._index)
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        await self._data.async_add_item(self._index, item.summary or "")

    async def async_update_todo_item(self, item: TodoItem) -> None:
        if item.summary is not None:
            await self._data.async_rename_item(self._index, item.uid, item.summary)
        if item.status is not None:
            # HA liefert je nach Aufrufer entweder ein TodoItemStatus-Enum
            # (z. B. aus dem Frontend) oder bereits einen rohen String (z. B.
            # aus dem todo.update_item Service) - beides robust behandeln.
            status_value = (
                item.status.value if isinstance(item.status, TodoItemStatus) else item.status
            )
            await self._data.async_apply_item_status(self._index, item.uid, status_value)

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        await self._data.async_delete_items(self._index, uids)
