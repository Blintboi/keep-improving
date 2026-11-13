"""Local input-idle policy for usage measurement, separate from restrictions."""
from dataclasses import replace


class MediaActivity:
    """Treat audible playback as input without changing the operating system."""
    def __init__(self):self.last_media=None

    def sample(self,sample,enabled,playing):
        if not enabled:
            self.last_media=None
            return sample
        if playing:self.last_media=sample
        if self.last_media is None:return sample
        awake_elapsed=sample.awake-self.last_media.awake
        if awake_elapsed<0:
            self.last_media=None
            return sample
        # Sleep must expire the grace period even though the tracking clock
        # intentionally excludes suspended time.
        elapsed=max(awake_elapsed,(sample.wall-self.last_media.wall).total_seconds())
        return replace(sample,idle_seconds=min(sample.idle_seconds,elapsed))


def timeout(settings):
    return settings.idle_timeout_seconds if settings.pause_when_idle else 0


def allows_interval(previous,current,seconds):
    # Never attribute the idle gap to the first input on return. Include the
    # interval ending exactly at the threshold, then stop on the next tick.
    return not seconds or previous.idle_seconds < seconds and current.idle_seconds <= seconds
