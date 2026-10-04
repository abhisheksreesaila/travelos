"""What the model is expected to answer for the captain's real Universal Studios and California Adventure messages (tests/fixtures/universal_dca.txt),
written by hand to the Convert schema (gitaway/canvas.py SCHEMA). Tests feed it through a fake transport; no test calls the real model."""

import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "universal_dca.txt"


def text() -> str:
    return FIXTURE.read_text()


def S(title, who=(), note=None, kind="ride", time=None):
    return {"title": title, "time": time, "who_raw": list(who), "note": note, "kind": kind}


def P(name, steps, tod=None):
    return {"name": name, "time_of_day": tod, "steps": steps}


def model_answer() -> dict:
    return {
        "days": [
            {"label": "Universal studios itinerary", "park_or_place": "Universal Studios Hollywood", "parts": [
                P("Lower Lot", [S("Super Nintendo World: Mario Kart"), S("Revenge of the Mummy"), S("Transformers 3D", note="roughest ride"),
                                S("Jurassic World: The Ride", who=["Hrishi"], note="water ride")], "Morning"),
                P("Lunch", [], "Around 12:00"),
                P("Harry Potter world", [S("Forbidden Journey"), S("Hippogriff", who=["H", "B"], note="H and B walk")], "Afternoon"),
                P("Upper Lot", [S("King Kong"), S("Fast & Furious - Supercharged", note="main!!! (you wrote: Fast and furious)"), S("Kung Fu Panda"), S("Minion Mayhem"),
                                S("Secret Life of Pets"), S("Silly Swirly"), S("Super Silly Fun Land"), S("Waterworld", kind="show", note="upper lot")], "Afternoon")]},
            {"label": "DCA itinerary", "park_or_place": "Disney California Adventure", "parts": [
                P("Hollywood Land and Avengers Campus", [S("Guardians of the Galaxy"), S("Web Slingers")]),
                P("Cars Land", [S("Radiator Springs Racers")]),
                P("Pixar Pier", [S("Incredicoaster", who=["R", "A"]), S("Toy Story Midway Mania", who=["R", "A"])]),
                P("Lunch", [], "Around 12:00"),
                P("Grizzly Peak", [S("Grizzly River Run", who=["R", "A"]), S("Soarin'", who=["H"])]),
                P("Buena Vista", [S("The Little Mermaid"), S("World of Color", kind="show", note="Fountain show")])]}],
        "set_aside": [{"title": "Studio Tour", "reason": "you wrote: skip", "day": 0}, {"title": "Simpsons", "reason": "you wrote: skip", "day": 0}],
        "lists": [{"name": "Pregnancy-safe rides", "items": [
            {"title": "Toy Story Midway Mania", "note": "some find the spinning jerky, use personal judgment"}, {"title": "The Little Mermaid", "note": None},
            {"title": "Monsters, Inc. Mike & Sulley to the Rescue!", "note": None}, {"title": "Web Slingers", "note": None}, {"title": "Jessie's Critter Carousel", "note": None},
            {"title": "Golden Zephyr", "note": None}, {"title": "Inside Out Emotional Whirlwind", "note": None}, {"title": "Soarin' Around the World", "note": None}]}],
        "initials_found": ["H", "B", "R", "A", "Hrishi"],
        "notes_kept": ["roughest ride", "main!!!", "H and B walk", "lamp side"],
        "merged_repeats": 1,
    }


def azure_reply(answer=None, tin=900, tout=1500) -> tuple:
    """What Azure sends back for `answer`: (status, body text)."""
    return 200, json.dumps({"choices": [{"message": {"content": json.dumps(answer if answer is not None else model_answer())}}], "usage": {"prompt_tokens": tin, "completion_tokens": tout}})


class FakeAzure:
    """An `ai.TRANSPORT` that answers with `answer` (or raises it, if it is an exception) and remembers what it was sent."""

    def __init__(self, answer=None, failure=None):
        self.answer, self.failure, self.sent = answer, failure, []

    def __call__(self, url, headers, body, timeout):
        self.sent.append(json.loads(body))
        if self.failure:
            raise self.failure
        return azure_reply(self.answer)
