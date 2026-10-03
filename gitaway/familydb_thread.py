"""The family thread's tables (F-070): one thread per trip, and each person's notification preferences.

Part of the family database (gitaway.familydb appends THREAD_TABLES to its FAMILY_TABLES, like familydb_social), so a thread belongs to the
family and every member sees the same one. The logic is gitaway/familythread.py.
"""


class ThreadItem:
    """One entry of a trip's thread, oldest first by rowid. `kind` is "message" (someone wrote it), "change" (a card the app wrote when a plan
    was added, moved or removed) or "photo" (F-071 fills it: `payload` is JSON with a `url` and a `caption`). `author` is the member id
    ("" for nobody), `author_name` the first name as it was then. `payload` is JSON text, "" when there is none."""
    id: str
    trip_id: str
    kind: str
    author: str = ""
    author_name: str = ""
    text: str = ""
    payload: str = ""
    created_at: str


class ThreadPref:
    """What one person wants from the thread's pushes. `quiet` 1 turns them off. `last_push` is the epoch second of the last push sent to them
    and `pending` how many updates have waited since (they are told in one push when the window ends)."""
    user_id: str
    quiet: int = 0
    last_push: int = 0
    pending: int = 0


THREAD_TABLES = [(ThreadItem, "thread", "id"), (ThreadPref, "thread_prefs", "user_id")]
THREAD_INDEXES = [("thread", ["trip_id"], False, "ix_thread_trip")]
