"""F-094: a send carries a client id (`cid`), so a Retry after a lost reply, or a double tap, is one message. Same person + same trip + same id = the existing
item comes back and nothing is announced twice; another person's identical id is a separate message."""

from gitaway import plantalk
from tests.test_canvas import announced, azure  # noqa: F401 - fixtures
from tests.test_plantalk import ari, ids, trip  # noqa: F401 - fixtures and helper
from tests.test_thread import crew, push  # noqa: F401 - fixtures

FRAG = {"X-Fragment": "1"}


def test_a_message_sent_twice_with_the_same_client_id_is_saved_once(crew, push):
    client, ed, _ = crew
    form = {"text": "Meet at the gate", "cid": "abc123def456"}
    first = client.post("/trip/family/message", data=form, headers=FRAG)
    again = client.post("/trip/family/message", data=form, headers=FRAG)
    assert first.status_code == again.status_code == 200
    assert again.text.count("Meet at the gate") == 1 and 'data-cid="abc123def456"' in again.text   # the existing item comes back
    assert ed.get("/trip/family/thread").text.count("Meet at the gate") == 1


def test_the_same_client_id_from_another_person_is_a_separate_message(crew):
    client, ed, _ = crew
    client.post("/trip/family/message", data={"text": "Hi from Ari", "cid": "samecid00001"}, headers=FRAG)
    ed.post("/trip/family/message", data={"text": "Hi from Ed", "cid": "samecid00001"}, headers=FRAG)
    page = client.get("/trip/family/thread").text
    assert "Hi from Ari" in page and "Hi from Ed" in page


def test_a_plan_chat_message_sent_twice_with_one_client_id_is_saved_once(trip, ari):
    act, lunch, _ = ids(ari)
    form = {"act": act, "part": lunch, "text": "Table for six", "cid": "retry0000001"}
    trip.post("/trip/talk/message", data=form, headers=FRAG)
    again = trip.post("/trip/talk/message", data=form, headers=FRAG)
    assert again.status_code == 200 and again.text.count("Table for six") == 1
    assert [i["text"] for i in plantalk.items(ari, act, lunch)] == ["Table for six"]
