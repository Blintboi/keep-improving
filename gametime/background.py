"""Debounce background failures without putting technical details in the UI."""
import time

DISCOVERY_PROBLEM = "Some game information could not be updated. Refresh the library to try again."
HUB_PROBLEM = "Game shortcuts could not be updated. Refresh the library to try again."


class BackgroundFailures:
    """A successful attempt resets the clock for that particular operation."""
    PERSISTENT_SECONDS = 60
    MIN_ATTEMPTS = 3
    MAX_RETRIES = 6

    def __init__(self):
        self.failures = {}
        self.reported = set()

    def update(self, key, failed):
        if not failed:
            self.failures.pop(key, None)
            self.reported.discard(key)
            return 0
        now = time.monotonic()
        first, count = self.failures.get(key, (now, 0))
        count += 1
        self.failures[key] = first, count
        if count >= self.MIN_ATTEMPTS and now - first >= self.PERSISTENT_SECONDS:
            self.reported.add(key)
        return count

    @staticmethod
    def retry_delay(attempt):
        return min(2 ** min(attempt, 5), 30)
