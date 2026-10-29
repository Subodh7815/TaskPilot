import datetime as dt
import tempfile
import unittest
from pathlib import Path
from taskpilot import build_report, decompose_goal, execute_auto_task, progress
class DecompositionTests(unittest.TestCase):
    def test_study_goal_gets_seven_ordered_dated_steps(self):
        tasks = decompose_goal("Study for biology exam", "2027-02-14", today="2027-02-01")
        self.assertEqual(len(tasks), 7)
        self.assertEqual([t["order"] for t in tasks], list(range(1, 8)))
        self.assertEqual(tasks[-1]["target_date"], "2027-02-14")
        self.assertTrue(all(tasks[i]["target_date"] <= tasks[i + 1]["target_date"] for i in range(6)))
    def test_goal_templates_select_expected_auto_and_manual_steps(self):
        tasks = decompose_goal("Plan a community event", today="2027-02-01")
        self.assertIn("event", tasks[0]["title"].lower() + " " + tasks[0]["description"].lower())
        self.assertIn("auto", {t["type"] for t in tasks})
        self.assertIn("manual", {t["type"] for t in tasks})
    def test_invalid_due_date_is_rejected(self):
        with self.assertRaises(ValueError):
            decompose_goal("Write a story", "not-a-date", today="2027-02-01")
class ExecutionTests(unittest.TestCase):
    def test_timeline_auto_step_creates_real_artifact_and_marks_done(self):
        task = {"id": "t1", "title": "Build timeline", "tool": "timeline", "type": "auto", "status": "todo", "target_date": "2027-02-10", "effort_hours": 2}
        with tempfile.TemporaryDirectory() as directory:
            artifact = execute_auto_task(task, "Launch a project", [task], directory, today="2027-02-01")
            self.assertTrue(Path(directory, artifact["filename"]).is_file())
            self.assertEqual(task["status"], "done")
            self.assertIn("Launch a project", Path(directory, artifact["filename"]).read_text())
    def test_manual_task_cannot_be_auto_executed(self):
        task = {"id": "t2", "title": "Attend class", "type": "manual", "status": "todo"}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                execute_auto_task(task, "Study", [task], directory)
class ProgressAndReportTests(unittest.TestCase):
    def test_progress_counts_done_and_skipped_as_resolved(self):
        tasks = [{"status": "done"}, {"status": "skipped"}, {"status": "todo"}, {"status": "running"}]
        result = progress(tasks)
        self.assertEqual(result["percent"], 50)
        self.assertEqual(result["resolved"], 2)
    def test_report_separates_user_work_open_and_suggestions(self):
        state = {"goal": "Run a 5k", "created_at": "2027-02-01", "due_date": "2027-03-01", "tasks": [
            {"title": "Create schedule", "type": "auto", "status": "done", "artifact": {"filename": "schedule.md"}},
            {"title": "Complete run", "type": "manual", "status": "done"},
            {"title": "Review plan", "type": "manual", "status": "todo", "target_date": "2027-02-21"},
            {"title": "Extra", "type": "manual", "status": "skipped"},
        ]}
        report = build_report(state, today="2027-02-20")
        self.assertIn("schedule.md", report)
        self.assertIn("Complete run", report)
        self.assertIn("Review plan", report)
        self.assertIn("Extra", report)
        self.assertIn("Suggestion, not done", report)
if __name__ == "__main__":
    unittest.main()
