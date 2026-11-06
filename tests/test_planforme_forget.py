"""F-193 (D-161): `forget-person` removes a person's Plan it for me orders (the intake, the dates, the kids' ages are personal) and their Stripe event rows; a stranger's stay.
GitAway keeps no money record of its own beyond that: Stripe is the record of payments."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import forget_person as fp  # noqa: E402

from gitaway import planforme as pfm  # noqa: E402
from tests.test_forget_person import EMAIL, count, folder  # noqa: E402,F401  (the fixture)


@pytest.fixture
def prepared(client):
    with pfm._db():      # the real tables are in the live community database before the folder is copied
        pass


@pytest.fixture
def orders(prepared, folder):
    dst, uid, fid = folder
    c = sqlite3.connect(dst / "community.db")
    for oid, owner in (("a" * 16, uid), ("b" * 16, uid), ("c" * 16, "someone-else")):
        c.execute("INSERT INTO plan_orders (id, owner_user, tenant_id, email, status, intake, amount_cents, result, created_at, updated_at) VALUES (?, ?, ?, ?, 'ready', ?, 2900, ?, 'n', 'n')",
                  (oid, owner, fid, EMAIL if owner == uid else "someone@example.com", '{"where":"Disneyland, California","kids":[4,7]}', '{"title":"t"}'))
        c.execute("INSERT INTO plan_order_events (event_id, order_id, outcome, at) VALUES (?, ?, 'paid', 'n')", (f"evt_{oid[0]}", oid))
    c.commit()
    c.close()
    return dst, uid


@pytest.mark.parametrize("family", [False, True])
def test_a_persons_orders_and_their_event_rows_go_a_strangers_stay(orders, family):
    dst, uid = orders
    fp.run(dst, EMAIL, family=family, yes=True, out=lambda s: None)
    assert count(dst, "community.db", "SELECT group_concat(id) FROM plan_orders") == "c" * 16
    assert count(dst, "community.db", "SELECT group_concat(event_id) FROM plan_order_events") == "evt_c"


def test_a_dry_run_says_what_it_would_delete_and_deletes_nothing(orders):
    dst, uid = orders
    out = []
    fp.run(dst, EMAIL, out=out.append)
    text = "\n".join(out)
    assert "would delete: 2 x Plan it for me orders (the intake is personal; Stripe keeps the payment) (plan_orders)" in text
    assert "would delete: 2 x Plan it for me Stripe event ids of their orders (plan_order_events)" in text
    assert count(dst, "community.db", "SELECT count(*) FROM plan_orders") == 3
