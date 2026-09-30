"""Result threads enroll their creator without compromising final delivery."""
import asyncio
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cron.scheduler_delivery import _open_continuable_cron_thread


def _schedule(coro, loop):
    future = Future()
    try:
        future.set_result(asyncio.run(coro))
    except Exception as exc:
        future.set_exception(exc)
    return future


@pytest.mark.parametrize("membership_error", [None, RuntimeError("missing permission")])
def test_creator_enrollment_preserves_delivery_thread(monkeypatch, membership_error):
    monkeypatch.setattr("agent.async_utils.safe_schedule_threadsafe", _schedule)
    adapter = SimpleNamespace(
        create_handoff_thread=AsyncMock(return_value="777"),
        add_handoff_thread_member=AsyncMock(side_effect=membership_error),
    )
    job = {"id": "job", "name": "digest", "origin": {"user_id": "123"}}
    assert _open_continuable_cron_thread(job, adapter, "555", object()) == "777"
    adapter.add_handoff_thread_member.assert_awaited_once_with("777", "123")


def test_platform_without_enrollment_capability(monkeypatch):
    monkeypatch.setattr("agent.async_utils.safe_schedule_threadsafe", _schedule)
    adapter = SimpleNamespace(create_handoff_thread=AsyncMock(return_value="777"))
    assert _open_continuable_cron_thread({"id": "job"}, adapter, "555", object()) == "777"


def test_no_origin_user_does_not_enroll(monkeypatch):
    monkeypatch.setattr("agent.async_utils.safe_schedule_threadsafe", _schedule)
    adapter = SimpleNamespace(
        create_handoff_thread=AsyncMock(return_value="777"),
        add_handoff_thread_member=AsyncMock(),
    )
    assert _open_continuable_cron_thread({"id": "job"}, adapter, "555", object()) == "777"
    adapter.add_handoff_thread_member.assert_not_awaited()
