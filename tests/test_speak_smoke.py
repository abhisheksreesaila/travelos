"""F-072: the by-hand smoke run (gitaway/speak_smoke.py) builds its day with the app's own builder; this keeps the two from drifting apart."""

from gitaway import speak, speak_smoke
from tests.test_speak import DAY, ctx_of, day  # noqa: F401


def test_the_smokes_day_has_every_key_the_apps_day_has(day):
    real, canned = ctx_of(day["s"], DAY), speak_smoke.canned_day()
    assert set(canned) == set(real)


def test_the_smokes_day_is_valid_input_for_the_model_prompt_and_for_validate():
    ctx = speak_smoke.canned_day()
    shown = speak.context_for(ctx)
    assert shown["now"] == "14:00" and [p["id"] for p in shown["plans"]] == ["a1", "a2", "a3"]
    ops, dropped = speak.validate(ctx, [
        {"op": "move_plan", "id": "a3", "date": None, "start": "16:00", "end": "18:00"},
        {"op": "move_plan", "id": "a1", "date": "2026-10-18", "start": "10:00", "end": "12:00"},
        {"op": "set_step_who", "id": "s1", "who": ["Abhi", "Bhoomija", "Hrishi"]}])
    assert [o["op"] for o in ops] == ["move_plan", "move_plan", "set_step_who"] and not dropped, dropped
    speak.changes(ctx, ops)
