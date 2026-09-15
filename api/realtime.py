"""A production write happened somewhere - tell whoever is watching a live
screen, instead of making them wait for the next poll.

The bridge this needs and the reason it isn't three lines: route handlers in
this package are plain `def` (see api/main.py's own docstring) so they run on
worker threads, but the WebSocket connections this notifies live on the
single asyncio event loop uvicorn drives. A worker thread can't just
`await queue.put(...)` on a queue that belongs to another thread's event
loop - `loop.call_soon_threadsafe` is the documented, correct way to hand
work from one to the other, so that's what `notify()` does.

Deliberately in-process and in-memory: one uvicorn process serves one plant,
the same assumption ScopedSession and the rest of this app already make.
A subscriber that reconnects (a phone that walked out of WiFi range and
back) just gets a fresh queue and the next event whenever one happens; nothing
is replayed, because the reconnecting client's own next poll/query already
re-fetches the real state - this only exists to make that happen sooner than
the fallback interval would.
"""
import asyncio
import threading

_loop: asyncio.AbstractEventLoop | None = None
_subscribers: set[asyncio.Queue] = set()
_lock = threading.Lock()


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called once, from api/main.py's startup event (which itself runs on
    the loop uvicorn will keep using), so notify() has somewhere to deliver
    to even though it may be called from a worker thread."""
    global _loop
    _loop = loop


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=8)
    with _lock:
        _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    with _lock:
        _subscribers.discard(q)


def notify(event: str = "production-changed") -> None:
    """Safe to call from anywhere, including the sync route handlers that
    make up most of this app. Never raises: a screen that misses a live
    update still catches up on its own next poll, and that is a far smaller
    problem than a write failing because the person who happened to be
    watching a dashboard lost their WebSocket connection five minutes ago.
    """
    if _loop is None:
        return
    with _lock:
        subs = list(_subscribers)
    for q in subs:
        try:
            _loop.call_soon_threadsafe(q.put_nowait, event)
        except Exception:
            pass
