import asyncio
import json
import structlog


# ── WebSocket log broadcaster ────────────────────────────────────

class LogBroadcaster:
    """Collects log events and streams them to connected WebSocket clients."""

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[str]] = []

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=500)
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        self._queues.discard(q) if hasattr(self._queues, "discard") else None
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    def emit(self, event: str, **kwargs) -> None:
        msg = json.dumps({"event": event, **kwargs})
        for q in list(self._queues):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass  # slow consumer — drop rather than block


# Global broadcaster instance (shared across the app)
broadcaster = LogBroadcaster()


# ── structlog processor that forwards to broadcaster ─────────────

class BroadcastProcessor:
    def __call__(self, logger, method, event_dict: dict) -> dict:
        broadcaster.emit(
            event_dict.get("event", ""),
            **{k: v for k, v in event_dict.items() if k != "event"},
        )
        return event_dict


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            BroadcastProcessor(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
