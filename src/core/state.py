import threading
import time


class BackgroundJob:
    _lock = threading.Lock()
    _status = "idle"
    _results = (0, 0.0)
    _error = None
    _started_at = None
    _version = 0

    @classmethod
    def start(cls):
        with cls._lock:
            cls._status = "running"
            cls._error = None
            cls._started_at = time.monotonic()

    @classmethod
    def complete(cls, count, duration):
        with cls._lock:
            cls._status = "complete"
            cls._results = (count, duration)
            cls._started_at = None
            cls._version += 1

    @classmethod
    def fail(cls, error_msg):
        with cls._lock:
            cls._status = "error"
            cls._error = error_msg
            cls._started_at = None

    @classmethod
    def get_data(cls):
        with cls._lock:
            elapsed = time.monotonic() - cls._started_at if cls._started_at else 0.0
            return {
                "status": cls._status,
                "results": cls._results,
                "error": cls._error,
                "elapsed": elapsed,
                "version": cls._version,
            }

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._status = "idle"
            cls._error = None
            cls._started_at = None
