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

# Pro-Routine-Felder (innerhalb eines Eintrags in CONF_ROUTINES). Diese
# Werte sind ab v1.0 nur noch der EINMALIGE Startzustand einer Routine -
# danach ist der persistente Store (siehe __init__.py/KinderRoutinenData)
# die Quelle der Wahrheit, damit Aenderungen ueber den Options-Flow
# (Aufgaben/Bilder/Name/Frist/Wochentage) nicht durch einen Neuladevorgang
# wieder auf den urspruenglichen Einrichtungsstand zurueckfallen.
ROUTINE_NAME = "name"
ROUTINE_DEADLINE = "deadline"
ROUTINE_WEEKDAYS = "weekdays"
ROUTINE_TASKS = "tasks"
ROUTINE_TASK_IMAGES = "task_images"  # list[str|None], parallel zu ROUTINE_TASKS
ROUTINE_BASE_IMAGE = "base_image"  # Bild vor Routinenstart ("Grundbild")
ROUTINE_DONE_IMAGE = "done_image"  # Bild wenn alle Aufgaben erledigt sind

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

# Ordner unter config/www, in dem hochgeladene Aufgaben-/Routinenbilder
# dauerhaft abgelegt werden.
WWW_IMAGE_SUBDIR = "kinder_routinen"

# Eigener, garantiert kollisionsfreier URL-Pfad, unter dem images.py diese
# Bilder ausliefert. Home Assistants eingebauter /local-Pfad (config/www)
# wird von der frontend-Komponente NUR beim HA-Start registriert, und auch
# nur dann, wenn der Ordner zu diesem Zeitpunkt schon existiert - unser
# Bilderordner entsteht aber typischerweise erst beim ersten Bild-Upload,
# oft lange nach dem Start. Ueber /local ausgelieferte Bilder wuerden also
# bis zum naechsten HA-Neustart mit 404 fehlschlagen (in der Testinstanz
# live nachvollzogen). Deshalb registriert images.py diesen eigenen Pfad
# selbst und dynamisch beim ersten Upload - unabhaengig vom Ladezeitpunkt.
STATIC_URL_PATH = "/kinder_routinen_media"
