"""F-182 (M2): a family trip that was published (the editor retired in F-254, the rows and files it made remain) and then taken down by the captain is deleted with its trip: the public page and the
picture files go, the takedowns row stays. The page is set up through the models, as the retired editor left it."""

from gitaway import community, familydb, publish, session as ses
from tests.live_trips import live_trip
from tests.test_signin import person
from tests.test_trip_import import imported


def test_deleting_a_family_trip_removes_a_taken_down_page_and_its_files_too(client):
    imported(client)
    s = person()
    row, _, _ = live_trip(who="ari", title="Our family week")
    slug = row["slug"]
    folder = publish.root() / slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ("a" * 16 + "-display.jpg")).write_bytes(b"\xff\xd8x")
    with ses.family(s) as fam:
        trip_id = fam.trip_id
        with familydb.transaction(fam.db):
            familydb.run(fam.db, "INSERT INTO publications (trip_id, slug, published_by, published_at) VALUES (:t, :s, :u, :a)", t=trip_id, s=slug, u=s["user_id"], a=familydb.now())
    community.take_down(slug)
    publish.take_down_trip(s, trip_id)
    assert community.get(slug, hidden=True) is None and not (publish.root() / slug).exists()
