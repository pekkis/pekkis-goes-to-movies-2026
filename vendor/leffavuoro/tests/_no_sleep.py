"""A module's `time` with `sleep` recorded instead of waited.

Only the named module's reference is swapped, so the local test servers, which import
`time` themselves, still behave as they would. Everything but `sleep` is the real
module. A test that asserted a wait by timing it asserts the recorded seconds instead,
which states the same claim exactly and costs nothing.
"""
import time as _time


class Clock:
    def __init__(self):
        self.slept = []

    def sleep(self, seconds):
        self.slept.append(seconds)

    def __getattr__(self, name):
        return getattr(_time, name)


def patch(test, module):
    """Replace `module.time` for the length of `test`. -> the Clock, whose `slept` lists
    every sleep the module asked for, in order."""
    clock, real = Clock(), module.time
    module.time = clock
    test.addCleanup(setattr, module, "time", real)
    return clock
