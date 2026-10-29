import datetime as dt
import html
import json
import os
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
BASE = Path(__file__).resolve().parent
DATA_FILE = BASE / "data.json"
ARTIFACT_DIR = BASE / "artifacts"
LOCK = threading.RLock()
TEMPLATES = {
    "study": [("Map the material", "Break the subject into topics and gather your syllabus or study resources.", "checklist", 1), ("Build a study timeline", "Create a dated schedule with focused study blocks.", "timeline", 2), ("Study the first concepts", "Work through the foundations and note questions to revisit.", None, 2), ("Draft study notes", "Create an outline for notes, key concepts and questions.", "outline", 2), ("Practice and review", "Complete practice questions and revisit difficult topics.", None, 2), ("Check progress and reminders", "Review upcoming study milestones.", "reminders", 1), ("Complete a final review", "Do a final recap and confirm what still needs attention.", None, 2)],
    "project": [("Define the project scope", "Clarify the outcome, constraints and success criteria.", "checklist", 1), ("Build the project timeline", "Lay out milestones and target dates.", "timeline", 2), ("Prepare the project outline", "Draft a working structure, decisions and open questions.", "outline", 1), ("Complete the first milestone", "Do the first hands-on project work.", None, 3), ("Review and refine the work", "Check progress against the intended outcome.", None, 2), ("Check milestones and reminders", "Review the upcoming project dates.", "reminders", 1), ("Finalize and verify", "Finish remaining work and verify the result.", None, 2)],
    "event": [("Set the event essentials", "Define audience, purpose, date and key constraints.", "checklist", 1), ("Build the event timeline", "Create a dated preparation schedule.", "timeline", 2), ("Draft the event plan", "Outline the agenda, logistics and open decisions.", "outline", 2), ("Arrange event logistics", "Handle the real-world arrangements and coordination.", None, 3), ("Confirm participants and details", "Check the necessary people and arrangements.", None, 2), ("Review upcoming reminders", "See the remaining event milestones by date.", "reminders", 1), ("Run the event and wrap up", "Deliver the event and capture any follow-up.", None, 3)],
    "fitness": [("Set a safe starting point", "Choose a realistic target and note any constraints.", "checklist", 1), ("Build a training timeline", "Create a dated plan with recovery time.", "timeline", 2), ("Prepare training notes", "Outline sessions, cues and progress measures.", "outline", 1), ("Complete the first sessions", "Carry out the planned activity at a suitable pace.", None, 3), ("Review progress and adjust", "Reflect on how the plan is working.", None, 2), ("Check upcoming reminders", "Review the next training dates.", "reminders", 1), ("Complete the target and reflect", "Finish the goal and note what to carry forward.", None, 2)],
    "writing": [("Clarify the writing brief", "Set the audience, purpose and scope.", "checklist", 1), ("Build a writing timeline", "Schedule drafting, review and finalization.", "timeline", 1), ("Draft the writing outline", "Create a structure with sections and key points.", "outline", 2), ("Write the first draft", "Draft the main content in your own words.", None, 3), ("Revise and fact-check", "Improve clarity, structure and accuracy.", None, 2), ("Check writing reminders", "Review remaining writing milestones.", "reminders", 1), ("Finalize the piece", "Proofread and prepare the final version.", None, 2)],
    "general": [("Clarify the outcome", "Define what success looks like and what is in scope.", "checklist", 1), ("Build a dated timeline", "Create a schedule with achievable milestones.", "timeline", 2), ("Draft a working outline", "Organize the main steps, notes and open questions.", "outline", 1), ("Make a first concrete start", "Complete an initial hands-on step.", None, 2), ("Review progress", "Check what is working and what needs adjustment.", None, 1), ("Check upcoming reminders", "Review the remaining target dates.", "reminders", 1), ("Finish and reflect", "Complete remaining work and capture lessons.", None, 2)],
}
def _today(value=None):
    return dt.date.fromisoformat(value) if value else dt.date.today()
def decompose_goal(goal, due_date=None, today=None):
    goal = " ".join(str(goal).split()).strip()
    if not goal:
        raise ValueError("Enter a goal first.")
    start = _today(today)
    due = dt.date.fromisoformat(due_date) if due_date else start + dt.timedelta(days=14)
    if due < start:
        raise ValueError("Due date cannot be in the past.")
    match = re.search(r"\b(study|project|event|fitness|writing|write|run|workout|train)\b", goal.lower())
    category = match.group(1) if match else "general"
    if category == "write": category = "writing"
    if category in ("run", "workout", "train"): category = "fitness"
    tasks = []
    span = (due - start).days
    for index, (title, description, tool, effort) in enumerate(TEMPLATES[category]):
        target = start + dt.timedelta(days=round(span * (index + 1) / len(TEMPLATES[category])))
        tasks.append({"id": uuid.uuid4().hex[:10], "order": index + 1, "title": title, "description": description,
                      "type": "auto" if tool else "manual", "tool": tool, "effort_hours": effort,
                      "target_date": target.isoformat(), "status": "todo", "artifact": None, "completed_at": None})
    return tasks
def progress(tasks):
    resolved = sum(task.get("status") in ("done", "skipped") for task in tasks)
    return {"resolved": resolved, "total": len(tasks), "percent": round(100 * resolved / len(tasks)) if tasks else 0}
def execute_auto_task(task, goal, tasks, artifact_dir, today=None):
    if task.get("type") != "auto" or task.get("status") in ("done", "skipped"):
        raise ValueError("Only pending auto tasks can be run.")
    date = _today(today)
    directory = Path(artifact_dir)
    directory.mkdir(parents=True, exist_ok=True)
    tool = task.get("tool")
    if tool == "timeline":
        body = f"# Timeline: {goal}\n\n" + "\n".join(f"- {t['target_date']} — {t['title']} ({t.get('effort_hours', 0)}h)" for t in tasks)
    elif tool == "checklist":
        body = "# Checklist and resources\n\n" + "\n".join(f"- [ ] {t['title']}: {t['description']}" for t in tasks) + "\n\n## Resource prompts\n- Gather relevant guides, references or materials.\n- Record useful links or contacts here manually."
    elif tool == "outline":
        body = f"# Working notes: {goal}\n\n## Desired outcome\n{goal}\n\n## Outline\n" + "\n".join(f"{i}. {t['title']}\n   - {t['description']}" for i, t in enumerate(tasks, 1)) + "\n\n## Questions and notes\n- Add your own notes here."
    elif tool == "reminders":
        body = "# Reminder list\n\n" + "\n".join(f"- {t['target_date']} — {t['title']} [{t['status']}]" for t in sorted(tasks, key=lambda item: item["target_date"]))
    else:
        raise ValueError("Unknown built-in tool.")
    slug = re.sub(r"[^a-z0-9]+", "-", task["title"].lower()).strip("-")[:48] or "artifact"
    filename = f"{date.isoformat()}-{slug}-{task['id']}.md"
    (directory / filename).write_text(body + "\n", encoding="utf-8")
    task["status"] = "done"
    task["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    task["artifact"] = {"filename": filename, "label": task["title"]}
    return task["artifact"]
def build_report(state, today=None):
    now = _today(today)
    tasks = sorted(state.get("tasks", []), key=lambda t: t.get("order", 999))
    auto = [t for t in tasks if t.get("status") == "done" and t.get("type") == "auto"]
    manual = [t for t in tasks if t.get("status") == "done" and t.get("type") == "manual"]
    open_tasks = [t for t in tasks if t.get("status") in ("todo", "running")]
    skipped = [t for t in tasks if t.get("status") == "skipped"]
    overdue = [t for t in open_tasks if t.get("target_date", "9999") < now.isoformat()]
    lines = [f"# Completion report: {state.get('goal', 'Untitled goal')}", "", f"- Started: {state.get('created_at', '—')}", f"- Due: {state.get('due_date') or 'Not set'}", f"- Report date: {now.isoformat()}", "", "## Tasks done by TaskPilot"]
    lines += [f"- {t['title']} — artifact: `{t['artifact']['filename']}`" if t.get("artifact") else f"- {t['title']}" for t in auto] or ["- None yet."]
    lines += ["", "## Tasks done by you"]
    lines += [f"- {t['title']}" for t in manual] or ["- None yet."]
    lines += ["", "## Open tasks"]
    lines += [f"- {t['title']} (target {t['target_date']})" for t in open_tasks] or ["- None."]
    lines += ["", "## Skipped tasks"]
    lines += [f"- {t['title']}" for t in skipped] or ["- None."]
    lines += ["", "## Overdue items"]
    lines += [f"- {t['title']} (target {t['target_date']})" for t in overdue] or ["- None."]
    lines += ["", "## Suggestions (Suggestion, not done)", "- Review open tasks and adjust target dates if your circumstances changed.", "- Add your own notes and resource links to generated artifacts."]
    return "\n".join(lines) + "\n"
def load_state():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"goal": "", "created_at": None, "due_date": None, "tasks": [], "activity": []}
def save_state(state):
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, DATA_FILE)
def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass
    def send_json(self, payload, status=200):
        raw = json.dumps(payload).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write((BASE / "index.html").read_bytes()); return
        if path == "/api/state":
            with LOCK:
                state = load_state(); state["progress"] = progress(state.get("tasks", [])); state["today"] = dt.date.today().isoformat(); state["report"] = build_report(state)
                self.send_json(state)
            return
        if path.startswith("/artifact/"):
            name = Path(unquote(path[len("/artifact/"):])).name
            artifact = ARTIFACT_DIR / name
            if artifact.is_file():
                raw = artifact.read_bytes(); self.send_response(200); self.send_header("Content-Type", "text/markdown; charset=utf-8"); self.send_header("Content-Disposition", f'inline; filename="{name}"'); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        self.send_error(404)
    def do_POST(self):
        path = urlparse(self.path).path
        try:
            data = self.body()
            with LOCK:
                state = load_state()
                if path == "/api/goal":
                    tasks = decompose_goal(data.get("goal", ""), data.get("due_date") or None)
                    state = {"goal": " ".join(data["goal"].split()), "created_at": dt.date.today().isoformat(), "due_date": data.get("due_date") or None, "tasks": tasks, "activity": [{"at": stamp(), "message": "Goal plan created."}]}
                elif path.startswith("/api/task/"):
                    task = next((t for t in state.get("tasks", []) if t["id"] == path.split("/")[-1]), None)
                    if task is None: raise ValueError("Task not found.")
                    action = data.get("action")
                    if action == "run":
                        execute_auto_task(task, state["goal"], state["tasks"], ARTIFACT_DIR)
                        message = f"TaskPilot generated {task['artifact']['filename']} for “{task['title']}”."
                    elif action in ("done", "skip") and task["type"] == "manual":
                        task["status"] = "done" if action == "done" else "skipped"; task["completed_at"] = stamp() if action == "done" else None
                        message = f"You marked “{task['title']}” {task['status']}."
                    else: raise ValueError("That action is not available for this task.")
                    state.setdefault("activity", []).append({"at": stamp(), "message": message})
                elif path in ("/api/run-next", "/api/run-all"):
                    candidates = [t for t in state.get("tasks", []) if t.get("type") == "auto" and t.get("status") not in ("done", "skipped")]
                    for task in candidates[:1] if path.endswith("next") else candidates:
                        execute_auto_task(task, state["goal"], state["tasks"], ARTIFACT_DIR)
                        state.setdefault("activity", []).append({"at": stamp(), "message": f"TaskPilot generated {task['artifact']['filename']} for “{task['title']}”."})
                else: self.send_error(404); return
                save_state(state); state["progress"] = progress(state.get("tasks", [])); state["today"] = dt.date.today().isoformat(); state["report"] = build_report(state); self.send_json(state)
        except (ValueError, KeyError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)
if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", "8000"))), Handler)
    print(f"TaskPilot listening on port {server.server_address[1]}", flush=True)
    server.serve_forever()
