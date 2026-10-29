# TaskPilot

TaskPilot turns one goal into a dated list of smaller tasks, runs the steps it can do itself, tracks progress, and writes a completion report.

## What it does
- Breaks a goal into 5-8 tasks using fixed keyword templates. No AI calls, no external services.
- "Auto" tasks run built-in tools and save real files: a dated timeline, a checklist, a draft outline, and an in-app reminder list.
- "Manual" tasks are things only you can do. You mark them done or skipped.
- Progress bar, overdue flags and a timestamped activity log.
- A Markdown completion report that separates what TaskPilot did, what you did, what is open, and suggestions (labelled "Suggestion, not done").

## What it does not do
It does not send email, post anywhere, send notifications or touch outside accounts. Reminder lists are in-app only.

## Run it
Python 3 standard library only.

    python3 taskpilot.py          # serves on 127.0.0.1:8000 (set PORT to change)
    python3 -m unittest -v        # 7 tests

Data is saved in data.json and generated files in artifacts/ next to the code.
