"""Cache-only recovery: real SDK serialization and existing SQLite payload."""
import json
from pathlib import Path
from dataclasses import replace
import pytest
from gateway.config import PlatformConfig
from gateway.platforms.base import cache_image_from_bytes
from gateway.platforms.event import MessageEvent
from gateway.work_router.models import CanonicalEvent
from gateway.work_router.service import WorkRouter
from gateway.work_router.config import RouterConfig, DEFAULT_PROFILES
from plugins.platforms.slack.adapter import SlackAdapter
from tests.gateway.work_router.test_tsk62_media_profile_closure import homes, PNG, RecordingSDK

@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['none', 'missing', 'corrupt', 'denied', 'team', 'identity', 'legacy'])
async def test_cache_recovery(homes, tmp_path, monkeypatch, failure):
    adapter = SlackAdapter(PlatformConfig(enabled=True, token='offline'))
    sdk = RecordingSDK('offline')
    adapter._team_clients['TTEST'] = sdk
    path = cache_image_from_bytes(PNG, '.png')
    stamp = Path(path).stat().st_mtime_ns
    event = CanonicalEvent('EvRestart', 'CEXEC', '1', text='Hans inspect', metadata={'slack_team_id': 'TTEST'})
    raw = {'files': [{'id': 'FFIXTURE'}], '_work_router_collected_refs': [{'id': 'FFIXTURE', 'path': path, 'kind': 'image'}]}
    native = MessageEvent(text=event.text, media_urls=[path], media_types=['image/png'], message_id='1')
    assert adapter._retain_work_router_native_context(event, raw, native)
    config = RouterConfig.from_mapping({'enabled': True, 'channel_allowlist': ['CEXEC'], 'db_path': str(tmp_path/'restart.db'), 'bot_registry': {n: f'UBOT{i}' for i,n in enumerate(DEFAULT_PROFILES)}})
    router = WorkRouter(config)
    journal = router.store.ack_journal
    original = journal.prepare(event, 'env')['payload_hash']
    journal.require_native_context(event.event_id, adapter._work_router_native_reference(event.event_id))
    payload = journal.get(event.event_id)['payload_json']
    assert journal.prepare(event, 'retry')['payload_hash'] == original
    assert path not in payload and 'files.slack.com' not in payload and 'offline' not in payload
    router.store.close()
    reopened = WorkRouter(config)
    try:
        restored = CanonicalEvent.from_dict(json.loads(reopened.store.ack_journal.get(event.event_id)['payload_json']))
        fresh = SlackAdapter(PlatformConfig(enabled=True, token='offline'))
        fresh._team_clients['TTEST'] = sdk
        if failure == 'missing': Path(path).unlink()
        if failure == 'corrupt': Path(path).write_bytes(PNG + b'corrupt')
        if failure == 'denied':
            original_wire = sdk._request
            async def denied(**kw):
                return {'data': {'ok': False, 'error': 'file_not_found'}, 'headers': {}, 'status_code': 200}
            monkeypatch.setattr(sdk, '_request', denied)
        if failure == 'team': fresh._team_clients.clear()
        if failure == 'identity': restored = replace(restored, thread_ts='other')
        if failure == 'legacy': restored.metadata.pop('_native_reference')
        if failure != 'none':
            with pytest.raises((RuntimeError, OSError, ValueError)):
                await fresh._work_router_media_context(restored, 'Hans')
        else:
            value = await fresh._work_router_media_context(restored, 'Hans')
            assert value['media_urls'] == [path]
            assert Path(path).read_bytes() == PNG and Path(path).stat().st_mtime_ns == stamp
            assert sdk.file_checks == [('offline', 'FFIXTURE')]
        fresh._work_router = reopened
        fresh.detach_work_router(reopened)
        assert not getattr(fresh, '_work_router_native_contexts', {})
    finally:
        reopened.store.close()
