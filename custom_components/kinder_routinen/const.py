"""Constants for die Kinder-Routinen Punktesystem integration."""

DOMAIN = "kinder_routinen"

# Config-Entry-Ebene (ein Entry = ein Kind)
CONF_KIND_NAME = "kind_name"
CONF_NOTIFY_TARGET = "notify_target"
CONF_ROUTINE_COUNT = "routine_count"
CONF_BONUS_ENABLED = "bonus_enabled"
CONF_BONUS_POINTS = "bonus_points"
CONF_ROUTINES = "routines"
CONF_DASHBOARD_URL_PATH = "dashboard_url_path"
CONF_DASHBOARD_ID = "dashboard_id"

# Pro-Routine-Felder (innerhalb eines Eintrags in CONF_ROUTINES)
ROUTINE_NAME = "name"
ROUTINE_DEADLINE = "deadline"
ROUTINE_WEEKDAYS = "weekdays"
ROUTINE_TASKS = "tasks"

WEEKDAY_OPTIONS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAY_LABELS_DE = {
    "mon": "Montag",
    "tue": "Dienstag",
    "wed": "Mittwoch",
    "thu": "Donnerstag",
    "fri": "Freitag",
    "sat": "Samstag",
    "sun": "Sonntag",
}

STORAGE_VERSION = 1

MAX_ROUTINES = 6

# "Schöne" Wochenziele, aus denen der Assistent das naheliegendste vorschlägt
NICE_WEEKLY_TARGETS = [30, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500]
