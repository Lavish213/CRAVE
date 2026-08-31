"""Static guard: the orchestrator's advanced-escalation call into
menu_extraction_router.extract_menu must always pass allow_llm_fallback=False.

This is a source-inspection test rather than a full run_for_place() mock,
matching the existing AST-guard pattern for the price-contract regression
(test_menu_extraction_observability.py). The escalation call site is deep
inside a large method with heavy DB/network setup; asserting the actual
keyword argument in the source is more robust against refactors than
mocking every collaborator just to observe one kwarg.
"""
from __future__ import annotations

import ast
from pathlib import Path


ORCHESTRATOR_PATH = (
    Path(__file__).parents[1]
    / "app"
    / "services"
    / "menu"
    / "processing"
    / "menu_orchestrator.py"
)


def _find_extract_menu_advanced_calls(tree: ast.AST) -> list[ast.Call]:
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name == "_extract_menu_advanced":
            calls.append(node)
    return calls


def test_advanced_escalation_call_locks_llm_fallback_off():
    tree = ast.parse(ORCHESTRATOR_PATH.read_text(encoding="utf-8"))
    calls = _find_extract_menu_advanced_calls(tree)

    assert calls, "expected at least one _extract_menu_advanced(...) call in menu_orchestrator.py"

    for call in calls:
        kwarg = next(
            (kw for kw in call.keywords if kw.arg == "allow_llm_fallback"),
            None,
        )
        assert kwarg is not None, (
            "menu_orchestrator.py's _extract_menu_advanced(...) call must pass "
            "allow_llm_fallback explicitly -- the free-route lock depends on "
            "this, not on the function default."
        )
        assert isinstance(kwarg.value, ast.Constant) and kwarg.value.value is False, (
            "menu_orchestrator.py must pass allow_llm_fallback=False "
            "(the scheduled/bulk enrichment path must never bill an LLM per miss)"
        )
