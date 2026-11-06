"""A real published trip without going through the editor: for the F-184 to F-186 tests, which care about what happens after a trip is live."""

from gitaway import community
from gitaway.itineraries import Day, Itinerary, Polaroid, Stop
from tests.test_signin import person


def live_trip(who="maya@example.com", name="Maya Chen", title="Three easy days in Santa Monica", photo=False, place="Los Angeles, California", plan_to="la"):
    """Publish a real trip for `who` (a dev sign-in email) and return (the community row, the creator's handle, the person's session)."""
    s = person(who)
    creator = community.claim_creator(s["user_id"], name)
    slug = f"{community.slugify(title)}-a1b2c3"
    pics = [Polaroid("/assets/photos/venice-beach-los-angeles-hero.jpg", "A photo from the post", "")] if photo else []
    trip = Itinerary(slug=slug, title=title, headline=f"{title}:", accent=f"{name.split()[0]}'s trip", place=place, lede="Three days from the post.",
                     days=[Day(1, "DAY 1", "The pier", "", [Stop("10:00 AM", "Santa Monica Pier"), Stop("12:30", "Lunch on Abbot Kinney"), Stop("17:30", "Sunset at the pier")], collapsed=False)],
                     stats=[("1 day", "from the post")], polaroids=pics, author=name, real=True, handle=creator["handle"], plan_to=plan_to, plan_days=3)
    row = community.publish(s, trip, kind="scrapbook", meta={"handle": creator["handle"], "name": name, "place": plan_to})
    return row, creator["handle"], s
