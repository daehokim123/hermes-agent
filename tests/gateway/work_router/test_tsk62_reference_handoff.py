"""Current attachment reference handoff: real pipeline, offline Slack wire only."""
import pytest
from tests.gateway.work_router.test_tsk62_media_profile_closure import (
    homes, RecordingSDK, test_router_consumed_context_reaches_only_selected_profile as run_pipeline,
)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['image', 'document'])
async def test_current_reference_reaches_owner(homes, tmp_path, monkeypatch, kind):
    await run_pipeline(homes, tmp_path, monkeypatch, 'Hans', kind)


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['none', 'missing', 'restart', 'revoked', 'other_owner', 'identity', 'prior', 'other_profile'])
async def test_reference_boundaries(homes, tmp_path, monkeypatch, failure):
    import json
    from dataclasses import replace
    from pathlib import Path
    from unittest.mock import AsyncMock
    from gateway.platforms.base import cache_image_from_bytes
    from gateway.platforms.event import MessageEvent
    from gateway.work_router.models import CanonicalEvent
    from gateway.work_router.service import WorkRouter
    from gateway.work_router.config import RouterConfig
    from gateway.config import PlatformConfig
    from plugins.platforms.slack.adapter import SlackAdapter
    from tests.gateway.work_router.test_tsk62_media_profile_closure import PNG

    adapter = SlackAdapter(PlatformConfig(enabled=True, token='offline'))
    path = cache_image_from_bytes(PNG, '.png')
    stamp = Path(path).stat().st_mtime_ns
    ev = CanonicalEvent('EvBound', 'CEXEC', '1', text='Hans, inspect', metadata={'slack_team_id': 'TTEST'})
    raw = {'files': [{'id': 'F1'}], '_work_router_collected_refs': [
        {'id': 'F1', 'url': 'https://files.slack.com/original', 'path': path, 'kind': 'image'}]}
    native = MessageEvent(text=ev.text, media_urls=[path], media_types=['image/png'], message_id='1', channel_context='prior text')
    if failure == 'prior':
        raw['_work_router_prior_media'] = True
    if failure == 'other_profile':
        foreign = homes / 'profiles' / 'Wendy' / 'foreign.png'
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_bytes(PNG)
        native.media_urls = [str(foreign)]
        raw['_work_router_collected_refs'][0]['path'] = str(foreign)
    accepted = adapter._retain_work_router_native_context(ev, raw, native)
    if failure in {'prior', 'other_profile'}:
        assert not accepted
        return
    assert accepted
    from gateway.work_router.config import DEFAULT_PROFILES
    config = RouterConfig.from_mapping({'enabled': True, 'channel_allowlist': ['CEXEC'], 'db_path': str(tmp_path / 'boundary.db'), 'bot_registry': {n: f'UBOT{i}' for i, n in enumerate(DEFAULT_PROFILES)}})
    router = WorkRouter(config)
    try:
        journal = router.store.ack_journal
        original = journal.prepare(ev, 'envelope')['payload_hash']
        journal.require_native_context(ev.event_id)
        assert journal.get(ev.event_id)['payload_hash'] == original
        assert journal.prepare(ev, 'retry-envelope')['payload_hash'] == original
        payload = journal.get(ev.event_id)['payload_json']
        assert path not in payload and 'files.slack.com' not in payload and 'prior text' not in payload
        restored = CanonicalEvent.from_dict(json.loads(payload))
        assert restored.metadata['_native_context_required'] is True
        from types import SimpleNamespace
        permission = AsyncMock(return_value={'ok': True, 'file': {'id': 'F1', 'url_private': 'https://files.slack.com/rotated'}})
        adapter._team_clients['TTEST'] = SimpleNamespace(files_info=permission)
        if failure == 'missing':
            Path(path).unlink()
        elif failure == 'restart':
            adapter._work_router_native_contexts.clear()
        elif failure == 'revoked':
            permission.return_value = {'ok': False}
        elif failure == 'other_owner':
            await adapter._work_router_media_context(restored, 'Hans')
        elif failure == 'identity':
            restored = replace(restored, thread_ts='another-thread')
        if failure != 'none':
            with pytest.raises((RuntimeError, OSError)):
                await adapter._work_router_media_context(restored, 'Wendy' if failure == 'other_owner' else 'Hans')
        else:
            value = await adapter._work_router_media_context(restored, 'Hans')
            assert Path(value['media_urls'][0]).read_bytes() == PNG
            assert value['message_id'] == '1' and value['channel_context'] == 'prior text'
            assert Path(path).stat().st_mtime_ns == stamp
            assert await adapter._work_router_media_context(restored, 'Hans') == value
    finally:
        router.store.close()
