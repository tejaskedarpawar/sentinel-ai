"""
Metadata Collector (live / real endpoint mode) — Linux target.

This is a genuine collector, not a simulation: it reads real process
and network counters via psutil and watches a real directory for file
events via watchdog (which uses inotify on Linux). It never reads file
contents — only the event type, size, and extension category — which
is exactly the metadata-only constraint Sentinel AI is built around.

Point WATCH_DIR at a real upload/sync folder in production (e.g. the
user's Downloads or a monitored shared-drive mount). Each event is
pushed onto the same Redis queue the simulator uses, so the rest of
the pipeline (profiling -> detection -> risk -> agent) treats live and
simulated events identically.

Usage:
    collector = LiveCollector(employee_id="EMP-LIVE", watch_dir="/tmp/sentinel_watch")
    collector.start()
    ...
    collector.stop()
"""
import os
import time
import threading
from datetime import datetime

import psutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from app.queue import push_event

RISKY_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".pst", ".csv", ".xlsx", ".sql", ".bak"}


def _destination_for_path(path: str) -> str:
    """Infer a coarse destination label from where a file landed —
    never the filename/content itself, only the category, matching the
    'no content inspection' privacy constraint."""
    lowered = path.lower()
    if "dropbox" in lowered or "gdrive" in lowered or "google drive" in lowered:
        return "personal-cloud-sync"
    if "/media/" in lowered or "/mnt/usb" in lowered:
        return "usb-mass-storage"
    return "local-disk"


class _WatchHandler(FileSystemEventHandler):
    def __init__(self, employee_id: str):
        self.employee_id = employee_id

    def _emit_file_event(self, path: str):
        try:
            size_bytes = os.path.getsize(path) if os.path.exists(path) else 0
        except OSError:
            size_bytes = 0
        ext = os.path.splitext(path)[1].lower()
        push_event({
            "employee_id": self.employee_id,
            "event_type": "upload",
            "timestamp": datetime.utcnow(),
            "payload": {
                "size_mb": round(size_bytes / (1024 * 1024), 4),
                "destination": _destination_for_path(path),
                "file_count": 1,
                "risky_extension": ext in RISKY_EXTENSIONS,
            },
        })

    def on_created(self, event):
        if not event.is_directory:
            self._emit_file_event(event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            self._emit_file_event(event.src_path)


class LiveCollector:
    """Runs a watchdog Observer on `watch_dir` plus a background thread
    that samples real process/network metadata via psutil every
    `sample_interval_seconds`, pushing everything to the Redis queue."""

    def __init__(self, employee_id: str = "EMP-LIVE", watch_dir: str = "/tmp/sentinel_watch",
                 sample_interval_seconds: int = 5):
        self.employee_id = employee_id
        self.watch_dir = watch_dir
        self.sample_interval_seconds = sample_interval_seconds
        os.makedirs(self.watch_dir, exist_ok=True)

        self._observer = Observer()
        self._observer.schedule(_WatchHandler(employee_id), self.watch_dir, recursive=True)

        self._stop_flag = threading.Event()
        self._sampler_thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._last_net = psutil.net_io_counters()

    def _sample_loop(self):
        while not self._stop_flag.is_set():
            try:
                procs = list(psutil.process_iter(attrs=["pid", "create_time"]))
                now = time.time()
                new_procs = sum(1 for p in procs if now - (p.info.get("create_time") or now) < self.sample_interval_seconds)

                net = psutil.net_io_counters()
                sent_mb = (net.bytes_sent - self._last_net.bytes_sent) / (1024 * 1024)
                recv_mb = (net.bytes_recv - self._last_net.bytes_recv) / (1024 * 1024)
                self._last_net = net

                push_event({
                    "employee_id": self.employee_id, "event_type": "process",
                    "timestamp": datetime.utcnow(),
                    "payload": {"process_count": len(procs), "new_process_count": new_procs},
                })
                push_event({
                    "employee_id": self.employee_id, "event_type": "network",
                    "timestamp": datetime.utcnow(),
                    "payload": {"network_mb": round(sent_mb + recv_mb, 4),
                                "session_minutes": self.sample_interval_seconds / 60},
                })
            except Exception as exc:  # keep the collector alive even if one sample fails
                print(f"[live_collector] sample error: {exc}")
            self._stop_flag.wait(self.sample_interval_seconds)

    def start(self):
        # A real collector would read the OS's own login/session records;
        # this sandbox has no such session manager, so we log exactly one
        # login-equivalent event at collector start to complete the schema.
        push_event({
            "employee_id": self.employee_id, "event_type": "login",
            "timestamp": datetime.utcnow(),
            "payload": {"device_known": True, "geo_city": "Nagpur", "source": "live_collector_start"},
        })
        self._observer.start()
        self._sampler_thread.start()

    def stop(self):
        self._stop_flag.set()
        self._observer.stop()
        self._observer.join(timeout=5)
