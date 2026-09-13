"""Media failure stays actionable without running an Owner or publishing a final."""
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
from hermes_cli import profiles
from gateway.work_router.service import WorkRouter
from tests.gateway.work_router.test_tsk62_native_sender import bridge, config_at, client_at


@pytest.mark.asyncio
@pytest.mark.parametrize('failure,code', [
    (RuntimeError('media_source_unavailable'), 'media_source_unavailable'),
    (RuntimeError('media_context_unavailable'), 'media_context_unavailable'),
    (RuntimeError('media_cache_changed'), 'media_cache_changed'),
    (FileNotFoundError('PRIVATE_PATH_NOT_FOR_LOG'), 'media_cache_unavailable'),
])
async def test_failure_reason_survives_router_and_reopen(bridge, tmp_path, monkeypatch, failure, code):
    sender, adapter, original, state, decision = bridge
    event = replace(original, metadata={**original.metadata, '_native_context_required': True})
    monkeypatch.setattr(profiles, 'profile_exists', lambda name: True)
    adapter._work_router_media_context = AsyncMock(side_effect=failure)
    sender.runner._handle_message = AsyncMock()
    client = client_at(adapter, {'ok': True, 'ts': 'unused'})
    config, _ = config_at(tmp_path)
    router = WorkRouter(config)
    try:
        router.ack_gate.complete(event.event_id, success=True)
        await router.enqueue_after_ack(event)
        result = await router.process_once(event.event_id, sender=sender)
        assert result.status == 'quarantined'
        assert result.error == code
        row = router.store._conn.execute(
            'SELECT last_error FROM router_inbox WHERE event_id=?', (event.event_id,)).fetchone()
        assert row[0] == code
        assert 'PRIVATE_PATH' not in str(result)
        assert not client.calls
        sender.runner._handle_message.assert_not_awaited()
    finally:
        router.store.close()
    reopened = WorkRouter(config)
    try:
        await reopened.process_once(event.event_id, sender=sender)
        assert not client.calls
        sender.runner._handle_message.assert_not_awaited()
        assert adapter._work_router_media_context.await_count == 1
    finally:
        reopened.store.close()
