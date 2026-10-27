"""Architecture guard: only app/orchestrator may write run/task status (invariant #3)."""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
ALLOWED = APP / "orchestrator"
STATE_COLUMNS = {"status", "started_at", "finished_at", "total_attempts", "cancel_requested"}


def _violations(path: Path) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AugAssign | ast.AnnAssign):
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Attribute) and t.attr in STATE_COLUMNS:
                # Pydantic/Python objects own attributes named `status` too; flag only ORM-ish uses.
                found.append(
                    f"{path.relative_to(APP)}:{getattr(node, 'lineno', 0)} assigns .{t.attr}"
                )
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "update"
        ):
            found.append(f"{path.relative_to(APP)}:{node.lineno} uses update()")
    return found


def test_only_the_orchestrator_mutates_run_and_task_state() -> None:
    bad = []
    for path in APP.rglob("*.py"):
        if ALLOWED in path.parents:
            continue
        bad.extend(_violations(path))
    assert bad == [], "state writes outside app/orchestrator:\n" + "\n".join(bad)


def test_guard_detects_a_violation(tmp_path: Path) -> None:
    sample = tmp_path / "x.py"
    sample.write_text("def f(run):\n    run.status = 'FAILED'\n", encoding="utf-8")
    assert _violations_in(sample)


def _violations_in(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        n.targets[0].attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Assign)
        and isinstance(n.targets[0], ast.Attribute)
        and n.targets[0].attr in STATE_COLUMNS
    ]
