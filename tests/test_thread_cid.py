"""F-094: a send carries a client id (`cid`), so a Retry after a lost reply, or a double tap, is one message. Same person + same trip + same id = the existing
item comes back and nothing is announced twice; another person's identical id is a separate message."""

from gitaway import plantalk
from tests.test_canvas import announced, azure  # noqa: F401 - fixtures
from tests.test_plantalk import ari, ids, trip  # noqa: F401 - fixtures and helper
from tests.test_thread import crew, push  # noqa: F401 - fixtures

FRAG = {"X-Fragment": "1"}

