"""Start and stop for what every browser test class shares. Not a test module: the
leading underscore keeps it out of discovery."""
import atexit
import threading

from playwright.sync_api import sync_playwright

# How often serve_forever looks for a shutdown request. At the 0.5 s default each class's
# tearDownClass waited a median 0.29 s for it, about 20 s a leg over 73 classes (2026-10-14).
POLL = 0.05


def start(srv):
    """Serve `srv` on a daemon thread. -> srv"""
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": POLL},
                     daemon=True).start()
    return srv


def stop(srv):
    """Stop serving and close the listening socket."""
    srv.shutdown()
    srv.server_close()


_driver = None


def playwright():
    """The process's one Playwright driver, started on first use and stopped at exit.

    Each class still launches and closes its own browser: one WebKit browser kept across
    classes hung on navigation after 18 to 29 of them (2026-10-14)."""
    global _driver
    if _driver is None:
        _driver = sync_playwright().start()
        atexit.register(_driver.stop)
    return _driver
