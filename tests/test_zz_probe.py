from tests.test_trip_import import imported
from tests.test_trip_canvas import bare


def test_probe(client):
    imported(client)
    page = bare(client.get("/trip/canvas").text)
    i = page.index('class="cz-week"')
    print(page[i:i + 2600])
