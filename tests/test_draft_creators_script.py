"""F-194 (9): `pixi run draft-creators` made claim links that do not work on gitaway.me (its drafts stay in a local folder, and scripts/ is not in the image). It refuses to run anywhere but on
the live data folder and points at /admin on gitaway.me, where drafting works."""

import importlib.util
import os
from pathlib import Path

import pytest

from gitaway import creatorclaim as cc
from tests.test_creator_claim import ROOT, rows, setup  # noqa: F401 - the claim tests' fixtures

REFUSAL = ("pixi run draft-creators makes claim links that do not work on gitaway.me: it keeps the drafts in this machine's own folder, and the live site cannot see them.\n"
           "Draft for creators on the live site instead: open https://gitaway.me/admin, sign in with your admin email and use \"Draft for a creator\" (one link, or tick rows of the list).\n"
           "Only a machine whose GITAWAY_DATA_DIR is the live data folder (/data) may run this script.")


def script():
    spec = importlib.util.spec_from_file_location("draft_creators", ROOT / "scripts" / "draft_creators.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize("folder", [None, "", "data/db", "/tmp/somewhere", "/data2", "/data/db", "/"])
def test_it_refuses_anywhere_but_the_live_data_folder(client, capsys, monkeypatch, setup, folder):
    here = Path(os.environ["GITAWAY_DATA_DIR"])
    with monkeypatch.context() as m:      # the environment is the script's only input: nothing here may open the database at a made-up folder
        if folder is None:
            m.delenv("GITAWAY_DATA_DIR", raising=False)
        else:
            m.setenv("GITAWAY_DATA_DIR", folder)
        code = script().main([])
    assert code == 2 and capsys.readouterr().out.strip() == REFUSAL
    assert rows() == [] and not (here / "claim-links.csv").exists()


def test_it_refuses_before_it_asks_for_a_key(capsys, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.delenv("GITAWAY_DATA_DIR", raising=False)
    assert script().main([]) == 2 and "ANTHROPIC_API_KEY" not in capsys.readouterr().out


def test_on_the_live_data_folder_it_goes_ahead_to_the_key_check(capsys, monkeypatch):
    monkeypatch.setenv("GITAWAY_DATA_DIR", "/data")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert script().main([]) == 1 and "ANTHROPIC_API_KEY must be set" in capsys.readouterr().out      # the old first check: without a key it explains and stops


def test_the_trailing_slash_and_dots_do_not_matter(capsys, monkeypatch):
    monkeypatch.setenv("GITAWAY_DATA_DIR", "/data/")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert script().main([]) == 1


def test_the_docs_send_the_captain_to_admin_not_to_the_script():
    morning = (ROOT / "docs" / "morning.html").read_text(encoding="utf-8")
    step4 = morning[morning.index('<b class="t">4</b>'):].split("</div>")[0]
    assert "gitaway.me/admin" in step4 and "Run <code>pixi run draft-creators</code>" not in step4
    setup_doc = (ROOT / "docs" / "setup.md").read_text(encoding="utf-8")
    assert "use /admin on gitaway.me" in setup_doc.lower() and "pixi run draft-creators" in setup_doc and "refuses" in setup_doc
