from app.devices.bus import Bus, StateChanged, WentOffline


async def test_every_subscriber_gets_every_event():
    bus = Bus()
    a, b = bus.subscribe(), bus.subscribe()

    bus.publish(StateChanged(1, 5))

    assert a.get_nowait() == b.get_nowait() == StateChanged(1, 5)


async def test_a_slow_subscriber_loses_its_oldest_events_and_never_blocks():
    bus = Bus()
    slow = bus.subscribe(size=2)

    for rev in range(1, 6):
        bus.publish(StateChanged(1, rev))

    assert [slow.get_nowait().rev, slow.get_nowait().rev] == [4, 5]


async def test_unsubscribed_queues_get_nothing():
    bus = Bus()
    queue = bus.subscribe()
    bus.unsubscribe(queue)
    bus.unsubscribe(queue)  # twice is harmless

    bus.publish(WentOffline(1))

    assert queue.empty()
