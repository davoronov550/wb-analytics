"""ChannelNotifier tests (T085) — inject fake senders, no real IO."""

from notifications.adapters.outbound.notifiers import ChannelNotifier
from notifications.domain.alert import EMAIL


def _no_sleep(_seconds):
    pass


def test_sends_via_selected_channel():
    got = []
    notifier = ChannelNotifier(
        email=lambda m: got.append(("e", m)),
        telegram=lambda m: got.append(("t", m)),
        sleep=_no_sleep,
    )
    notifier.send(EMAIL, "hi")
    assert got == [("e", "hi")]


def test_retries_then_gives_up_without_raising():
    calls = []

    def boom(_message):
        calls.append(1)
        raise RuntimeError("down")

    ChannelNotifier(email=boom, retries=2, sleep=_no_sleep).send(EMAIL, "hi")
    assert len(calls) == 3  # first try + 2 retries, no exception


def test_succeeds_on_a_later_attempt():
    calls = []

    def flaky(_message):
        calls.append(1)
        if len(calls) < 2:
            raise RuntimeError("transient")

    ChannelNotifier(email=flaky, retries=2, sleep=_no_sleep).send(EMAIL, "hi")
    assert len(calls) == 2


def test_unknown_channel_is_noop():
    ChannelNotifier(sleep=_no_sleep).send("sms", "hi")  # must not raise
