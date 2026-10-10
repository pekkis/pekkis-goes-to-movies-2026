"""A private validator cache for one test.

`common` reads KINO_HTTP_CACHE into CACHE_DIR at import, and `fetch(cache=True)` reads and
writes there; `get_text` passes `cache=True` by default. A test that reaches a real server
with the cache on points both at a directory of its own, and both are put back when the
test ends. No test then depends on an earlier one having set the variable, and none writes
into the real `.http-cache`.
"""
import os
import pathlib
import tempfile

import _ctx                                                # noqa: F401
import common


def temp_cache(test):
    """Point `common` at a fresh directory for this test. -> that directory."""
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    path = pathlib.Path(tmp.name) / "http-cache"
    saved_env, saved_dir = os.environ.get("KINO_HTTP_CACHE"), common.CACHE_DIR

    def restore():
        if saved_env is None:
            os.environ.pop("KINO_HTTP_CACHE", None)
        else:
            os.environ["KINO_HTTP_CACHE"] = saved_env
        common.CACHE_DIR = saved_dir

    # Registered after the directory's cleanup, so it runs first: nothing points at the
    # directory once it is gone.
    test.addCleanup(restore)
    os.environ["KINO_HTTP_CACHE"] = str(path)
    common.CACHE_DIR = path
    return path
