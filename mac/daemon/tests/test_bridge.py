import asyncio
import threading
import time

from daemon import bridge


def test_broadcast_no_clients_is_noop():
    # Calling broadcast before any bridge exists must not raise.
    bridge.broadcast({"type": "status", "text": "x"})


def _teardown_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Cancel all tasks so the serve coroutine's async-with closes the WS
    server, then stop and close the loop. Waits for the daemon thread to
    finish so nothing is left pending."""
    done = threading.Event()

    async def _shutdown() -> None:
        # Let the loop process the queued broadcast task and finish server startup.
        for _ in range(100):
            await asyncio.sleep(0)
        me = asyncio.current_task()
        for t in asyncio.all_tasks(loop):
            if t is not me:
                t.cancel()
        while any(
            t is not asyncio.current_task() and not t.done()
            for t in asyncio.all_tasks(loop)
        ):
            await asyncio.sleep(0)
        done.set()
        loop.stop()

    loop.call_soon_threadsafe(lambda: asyncio.ensure_future(_shutdown(), loop=loop))
    assert done.wait(timeout=10), "bridge teardown timed out"
    time.sleep(0.05)  # let the daemon thread exit run_until_complete
    loop.close()


def test_start_bridge_then_broadcast_noop():
    bridge.start_bridge(on_command=None)
    try:
        bridge.broadcast({"type": "status", "text": "ok"})
    finally:
        if bridge._bridge_loop is not None:
            _teardown_loop(bridge._bridge_loop)
        if bridge._http_server is not None:
            bridge._http_server.shutdown()
            bridge._http_server.server_close()
        bridge._bridge_loop = None
        bridge._http_server = None
        bridge._clients.clear()
