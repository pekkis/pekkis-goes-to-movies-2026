"""Start and stop for what every browser test class shares. Not a test module: the
leading underscore keeps it out of discovery."""
import atexit
import struct
import threading
import zlib

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


def png(w, h, rgb=(40, 120, 200)):
    """A solid PNG of `w` x `h`, written with the standard library. CI's browser job has no
    Pillow, and a picture's drawn shape is only checkable against a real file's size."""
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
