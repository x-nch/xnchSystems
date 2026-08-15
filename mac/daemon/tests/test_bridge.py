from daemon import bridge


def test_broadcast_no_clients_is_noop():
    # Calling broadcast before any bridge exists must not raise.
    bridge.broadcast({"type": "status", "text": "x"})


def test_start_bridge_then_broadcast_noop():
    bridge.start_bridge(on_command=None)
    try:
        bridge.broadcast({"type": "status", "text": "ok"})
    finally:
        bridge._bridge_loop.call_soon_threadsafe(bridge._bridge_loop.stop)
        bridge._bridge_loop = None
        bridge._clients.clear()
