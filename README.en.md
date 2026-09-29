# Kids' Daily Routines with a Live Points System for Home Assistant

[🇩🇪 Deutsch](README.md) · 🇬🇧 English

[![Open your Home Assistant instance and add this repository to HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jacky-coke&repository=daily_routines&category=integration)

> "Did she brush her teeth?" becomes a dashboard that keeps score by
> itself: every task finished on time gives an instant point, the week adds
> up to a round target, and progress is visible as a picture – no more
> checklist taped to the fridge.

> **Note:** This English page covers the README only. The setup wizard and
> the integration's own screens are currently German-only (see
> [Roadmap](#roadmap)).

## What this integration does

- A **setup wizard** asks for the child's name, the routines (e.g.
  "Morning", "Midday") and the tasks per routine directly – no to-do list
  needs to be created by hand beforehand.
- Every task checked off **on time** (before a deadline you choose) gives
  **one point instantly** – not evaluated only in the evening.
- A **weekly counter** (resets to 0 every Monday) and a **points balance**
  (never resets) that rewards can later be redeemed against.
- At the end, the wizard automatically suggests a "round" weekly target
  (e.g. 100 instead of 87 points) – optionally topped up with bonus points
  for a fully on-time day.
- An optional **picture per task** can be uploaded, plus a base image and
  an "all done" image. The matching picture is shown automatically as soon
  as that task was the last one completed.
- Right after setup, a **dedicated dashboard** is created automatically in
  the sidebar – with to-do lists, points display and progress picture. No
  manual card-building required.
- Everything can be adjusted later via **"Configure"** on the entry:
  add or remove routines, edit tasks, swap pictures – without setting the
  integration up again.

## Why this project exists

The trigger was a very concrete situation at home: our daughter Ronja is
neurodivergent, and she finds it especially hard in the morning to break
down a bundled instruction like "get ready" into its individual steps and
work through them on her own.

There's a well-understood reason for that. Independently planning,
starting and following through on multi-step tasks falls under what's
called **executive function** – a group of cognitive skills that includes
action planning, task initiation and self-organization, among others. In
many neurodivergent children, for example with ADHD or on the autism
spectrum, these exact functions can be expressed differently (this
explanatory model is closely associated with ADHD researcher Russell
Barkley). For a child with these difficulties, an instruction like "get
ready" invisibly bundles seven, eight or more individual steps – each one
its own small decision the whole routine can get stuck on.

A well-established approach in special education and occupational therapy
is **task analysis**: a complex action is broken down into individual,
visible, checkable steps, combined with immediate, positive feedback after
each one. That's exactly what this project implements technically – a
clear, fixed list of tasks instead of one vague overall instruction, a
point right after each completed step instead of only in the evening, and
a progress picture that makes visible how close the goal already is.

One thing matters to me here: this is an everyday tool that technically
supports a proven strategy – it is not diagnosis or therapy. For questions
about individual support, a conversation with a pediatrician, occupational
therapist or the school's special-education team is always worthwhile.

## What it looks like in practice

![Dashboard example: routine list, progress picture and points gauge](images/dashboard-beispiel.png)

This is Ronja's real, daily-used dashboard – the checkable routine on the
left, the progress picture in the middle, the points gauge on the right.

**Important note:** this screenshot shows my own, organically grown
dashboard and goes beyond what the integration sets up automatically. It
additionally uses:

- the HACS card [`calendar-card-pro`](https://github.com/alexpfau/calendar-card-pro)
  for the calendar tiles ("Stundenplan"/timetable, "Schultermine des
  Tages"/today's school events, "Ronjas Termine"/Ronja's appointments),
- the custom integration [`ms365_calendar`](https://github.com/RogerSelwyn/MS365-Calendar)
  ("Microsoft 365 – Calendar" by RogerSelwyn, via HACS) to connect the
  Microsoft 365 calendar used for the timetable,
- the HACS card [`bar-card`](https://github.com/custom-cards/bar-card) for
  the vertical-bar style of the points gauge,
- a "redeem reward" picker plus a redeem button – part of my own,
  originally manually built setup, **not yet** part of this integration
  (see [Roadmap](#roadmap)),
- a custom, individually created picture series used as the progress
  picture (not part of this repo).

The integration itself provides a simpler, but immediately working, base
without these extras – details further below.

## Installation

- In HACS → "Custom repositories", add this repo's URL, category
  "Integration" (or use the badge above on this page).
- Restart Home Assistant.
- Go to **Settings → Devices & Services → Add Integration → "Kinder-Routinen
  Punktesystem"** – the wizard walks you through setup step by step: child
  name and number of routines, tasks per routine, optionally pictures per
  task, and finally the points system.

A detailed, step-by-step walkthrough of the wizard and of managing
everything afterwards lives in the
[integration's own README](custom_components/kinder_routinen/README.md)
(German only for now).

## Requirements

- Home Assistant (tested with current 2026.x versions)
- HACS, to install the integration

No further helpers, automations or custom cards are required – the
integration sets up everything it needs on its own.

## Repository layout

```
custom_components/kinder_routinen/   The integration itself (see its own README)
images/                              Example dashboard screenshot (see above)
```

## Roadmap

- Reward picker and redeem button as native parts of the integration
  (currently still built manually, see note above).
- A Friday weekly report with per-weekday status.
- A full English translation of the integration's own UI, not just this
  README.

## License

MIT – see [LICENSE](LICENSE). Do whatever you like with it; a mention is
appreciated but not required.
