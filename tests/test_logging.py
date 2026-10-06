"""F-104 review: gitaway.* loggers (gitaway.ask, gitaway.thread, gitaway.morning ...) reach `railway logs`. fh-saas's configure_logging only sets up `fh_saas`."""
import logging


def test_gitaway_loggers_have_a_handler_at_info_without_duplicates(client):
    import main  # noqa: F401  (importing the app sets the logging up)
    log = logging.getLogger("gitaway.ask")
    assert log.isEnabledFor(logging.INFO)
    top = logging.getLogger("gitaway")
    assert top.handlers and top.propagate is False                  # its own handler, and not the root's as well
    assert len([h for h in top.handlers if type(h) is logging.StreamHandler]) == 1
    assert all(h.level <= logging.INFO for h in top.handlers)
