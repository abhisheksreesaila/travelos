"""The trip canvas's tables (F-080): parts and steps inside a calendar block, and a trip's named lists.

Part of the family database (gitaway.familydb appends CANVAS_TABLES to its FAMILY_TABLES, like familydb_thread). A block is a calendar activity
(`act_id`, the short id "a5" the calendar uses, in the trip's own calendar: scope ""). The logic is gitaway/canvas.py.

`who` on a step is a JSON list of strings: "m:<member id>" for a family member, "n:<Name>" for someone who is not a member, "i:<R>" for initials
nobody matched. A step with an empty `part_id` hangs on the block itself (the Set aside tray holds such steps with aside = 1).
"""


class BlockPart:
    """An area or a stretch of a block ("Lower Lot", "Lunch", "Afternoon"), in `position` order. `time_of_day` is free text ("Morning", "Around 12:00") or ""."""
    id: str
    trip_id: str
    act_id: str
    position: int = 0
    name: str
    time_of_day: str = ""


class BlockStep:
    """A ride, show, meal or meet-up inside a block. `time` is "HH:MM" or "". `who` is JSON (see the module note). `kind` is ride, show, meal, meet
    or other. `done` and `aside` are 0 or 1; an aside step stays in the trip, in the block's Set aside tray."""
    id: str
    trip_id: str
    act_id: str
    part_id: str = ""
    position: int = 0
    title: str
    time: str = ""
    who: str = "[]"
    note: str = ""
    kind: str = "other"
    done: int = 0
    aside: int = 0
    created_at: str


class TripList:
    """A named list on a trip ("Pregnancy-safe rides"). `for_who` is "m:<member id>", "n:<Name>" or "" (just a list)."""
    id: str
    trip_id: str
    name: str
    for_who: str = ""
    position: int = 0


class TripListItem:
    id: str
    list_id: str
    trip_id: str
    title: str
    note: str = ""
    position: int = 0


CANVAS_TABLES = [(BlockPart, "block_parts", "id"), (BlockStep, "block_steps", "id"), (TripList, "trip_lists", "id"), (TripListItem, "trip_list_items", "id")]
CANVAS_INDEXES = [("block_parts", ["trip_id", "act_id"], False, "ix_block_parts_act"), ("block_steps", ["trip_id", "act_id"], False, "ix_block_steps_act"),
                  ("trip_lists", ["trip_id"], False, "ix_trip_lists_trip"), ("trip_list_items", ["list_id"], False, "ix_trip_list_items_list")]
