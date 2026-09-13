"""Recover cached contents without persisting document or prior-thread bodies."""
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from gateway.config import PlatformConfig
from gateway.platforms.base import cache_document_from_bytes, cache_image_from_bytes
from gateway.platforms.event import MessageEvent
from gateway.work_router.models import CanonicalEvent
from gateway.work_router.service import WorkRouter
from gateway.work_router.config import RouterConfig, DEFAULT_PROFILES
from plugins.platforms.slack.adapter import SlackAdapter
from tests.gateway.work_router.test_tsk62_media_profile_closure import homes, PNG, RecordingSDK


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['document', 'prior_image', 'changed_history', 'current_image_delta'])
async def test_enrichment_rebuilt_from_existing_source(homes, tmp_path, kind):
    adapter = SlackAdapter(PlatformConfig(enabled=True, token='offline'))
    event = CanonicalEvent('EvEnrichment', 'CEXEC', '1', text='Hans inspect', metadata={'slack_team_id': 'TTEST'})
    doc = kind == 'document'
    path = cache_document_from_bytes(b'private-doc-body', 'fixture.txt') if doc else cache_image_from_bytes(PNG, '.png')
    prior = kind in {'prior_image', 'changed_history'}
    with_history = not doc
    native = MessageEvent(text='[Content of fixture.txt]:\nprivate-doc-body\n\nHans inspect' if doc else event.text,
        media_urls=[path], media_types=['text/plain' if doc else 'image/png'], message_id='2',
        channel_context='private prior context' if with_history else None,
        metadata={'_work_router_context_scope': {'verified': True, 'after_ts': '0.5' if kind == 'current_image_delta' else None}})
    raw = {'files': [] if prior else [{'id': 'FFIXTURE'}], '_work_router_prior_media': prior,
        '_work_router_collected_refs': [{'id': 'FFIXTURE', 'path': path, 'kind': 'document' if doc else 'image',
            'prior': prior, 'name': 'fixture.txt' if doc else 'fixture.png'}]}
    assert adapter._retain_work_router_native_context(event, raw, native)
    config = RouterConfig.from_mapping({'enabled': True, 'channel_allowlist': ['CEXEC'],
        'db_path': str(tmp_path/'recover.db'), 'bot_registry': {n: f'UBOT{i}' for i,n in enumerate(DEFAULT_PROFILES)}})
    router = WorkRouter(config)
    try:
        router.store.ack_journal.prepare(event, 'env')
        router.store.ack_journal.require_native_context(event.event_id, adapter._work_router_native_reference(event.event_id))
        payload = router.store.ack_journal.get(event.event_id)['payload_json']
        assert 'private-doc-body' not in payload and 'private prior context' not in payload
    finally:
        router.store.close()
    reopened = WorkRouter(config)
    try:
        restored = CanonicalEvent.from_dict(json.loads(reopened.store.ack_journal.get(event.event_id)['payload_json']))
        fresh = SlackAdapter(PlatformConfig(enabled=True, token='offline'))
        fresh._team_clients['TTEST'] = RecordingSDK('offline')
        fresh._fetch_thread_context = AsyncMock(return_value='changed history' if kind == 'changed_history' else 'private prior context')
        if kind == 'changed_history':
            with pytest.raises(RuntimeError, match='media_context_unavailable'):
                await fresh._work_router_media_context(restored, 'Hans')
        else:
            value = await fresh._work_router_media_context(restored, 'Hans')
            assert value['media_urls'] == [path]
            if doc:
                assert 'private-doc-body' in value['text']
                fresh._fetch_thread_context.assert_not_awaited()
            else:
                assert value['channel_context'] == 'private prior context'
                expected = {'channel_id': 'CEXEC', 'thread_ts': '1', 'current_ts': '2', 'team_id': 'TTEST', 'force_refresh': True}
                if kind == 'current_image_delta':
                    expected['after_ts'] = '0.5'
                fresh._fetch_thread_context.assert_awaited_once_with(**expected)
    finally:
        reopened.store.close()
