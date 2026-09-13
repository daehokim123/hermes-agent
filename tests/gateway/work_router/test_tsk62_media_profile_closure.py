"""TSK62 real Bolt -> pre-ACK journal -> Router -> native Gateway media closure.

Only the Slack HTTP/socket wire and model execution are recorded substitutes.
All original Owner/media/text/dedup assertions remain enforced.
"""
import base64
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from slack_bolt.async_app import AsyncApp
from slack_bolt.authorization.authorize_result import AuthorizeResult
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.web.async_client import AsyncWebClient

from agent import secret_scope
from gateway.config import GatewayConfig, Platform, PlatformConfig
from gateway.run import GatewayRunner, _profile_runtime_scope
from gateway.work_router.config import DEFAULT_PROFILES, RouterConfig
from gateway.work_router.native_sender import NativeRouterSender
from gateway.work_router.service import WorkRouter
from hermes_cli.profiles import get_profile_dir
from hermes_constants import get_hermes_home
from plugins.platforms.slack.adapter import SlackAdapter

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class RecordingSDK(AsyncWebClient):
    """Keep SDK request building/response validation; replace network I/O only."""
    def __init__(self, token):
        super().__init__(token=token)
        self.wire = []

    async def _request(self, *, http_verb, api_url, req_args):
        if api_url.endswith('/files.info'):
            file_id = req_args['params']['file']
            self.file_checks = getattr(self, 'file_checks', []) + [(self.token, file_id)]
            assert file_id == 'FFIXTURE'
            return {'data': {'ok': True, 'file': {'id': file_id,
                'url_private': 'https://files.slack.com/rotated-authorized-url'}},
                'headers': {}, 'status_code': 200}
        assert api_url.endswith('/chat.postMessage'), api_url
        self.wire.append((api_url, req_args, list(self.retry_handlers)))
        return {'data': {'ok': True, 'ts': '1700000001.0'}, 'headers': {}, 'status_code': 200}


@pytest.fixture
def homes(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: tmp_path))
    root = tmp_path / 'runtime-home'
    root.mkdir()
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('HERMES_HOME', str(root))
    monkeypatch.delenv('HERMES_PROFILE', raising=False)
    monkeypatch.setattr(secret_scope, '_MULTIPLEX_ACTIVE', True)
    monkeypatch.setenv('TSK62_AMBIENT_ONLY', 'must-not-borrow')
    for name in ('default', *DEFAULT_PROFILES):
        home = get_profile_dir(name)
        home.mkdir(parents=True, exist_ok=True)
        (home / 'config.yaml').write_text('{}\n')
        (home / '.env').write_text(f'TSK62_OWNER={name}\nSLACK_ALLOW_ALL_USERS=true\n')
        (home / 'owner.txt').write_text(name)
    return root


@pytest.mark.asyncio
@pytest.mark.parametrize('target', DEFAULT_PROFILES)
@pytest.mark.parametrize('kind', ['text', 'mention', 'image', 'document', 'thread_image'])
async def test_router_consumed_context_reaches_only_selected_profile(homes, tmp_path, monkeypatch, target, kind):
    """No synthetic classifier: real Router decides and real Gateway persists the turn."""
    from tools import url_safety
    config = RouterConfig.from_mapping({
        'enabled': True, 'channel_allowlist': ['CEXEC'],
        'db_path': str(tmp_path / 'router.db'),
        'bot_registry': {n: f'UBOT{i}' for i, n in enumerate(DEFAULT_PROFILES)},
    }).require_ready()
    router = WorkRouter(config)
    runner = GatewayRunner(GatewayConfig(sessions_dir=homes / 'sessions', multiplex_profiles=True))
    adapter = SlackAdapter(PlatformConfig(enabled=True, token='xoxb-recorded-receiver', extra={
        'require_mention': False, 'ignore_other_user_mentions': False,
    }))
    adapter._running = True
    adapter._bot_user_id = 'UBOT0'
    adapter._app_token = 'xapp-recorded'
    adapter._proxy_url = None
    adapter._resolve_user_is_bot = AsyncMock(return_value=False)
    adapter._resolve_user_name = AsyncMock(return_value='Sender')
    adapter._resolve_channel_name = AsyncMock(return_value='fixture')
    adapter.stop_typing = AsyncMock()
    adapter.handle_message = AsyncMock(side_effect=AssertionError('Router must retain ownership'))
    adapter.attach_work_router(router)
    runner.adapters[Platform.SLACK] = adapter
    sdk = RecordingSDK(adapter.config.token)
    adapter._team_clients['TTEST'] = sdk
    adapter._get_client = lambda *a, **kw: sdk

    async def authorize(enterprise_id, team_id, user_id):
        return AuthorizeResult(enterprise_id=enterprise_id, team_id=team_id,
                               bot_token=adapter.config.token, bot_user_id='UBOT0')
    adapter._app = AsyncApp(authorize=authorize, process_before_response=True)
    adapter._register_bolt_handlers()
    sender = NativeRouterSender(runner)
    sender.bind(adapter)
    downloads, built, native, model = [], [], [], []

    def download(request):
        downloads.append((str(request.url), request.headers['Authorization'], get_hermes_home()))
        data = b'fixture-document-body' if kind == 'document' else PNG
        return httpx.Response(200, content=data, headers={'content-type': 'text/plain' if kind == 'document' else 'image/png'})
    # No DNS or real HTTP: real adapter token/CDN checks, HTTP request and cache writes remain.
    monkeypatch.setattr(url_safety, 'is_safe_url', lambda url: True)
    monkeypatch.setattr(url_safety, 'create_ssrf_safe_async_client',
                        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(download), **kw))
    if kind == 'thread_image':
        from plugins.platforms.slack.adapter import _ThreadContextCache
        adapter._thread_context_cache[adapter._thread_cache_key('CEXEC', '1700000000.1', 'TTEST')] = _ThreadContextCache(
            content='fixture prior context', messages=[{'ts': '1700000000.1', 'text': 'prior image',
            'files': [{'id': 'FFIXTURE', 'mimetype': 'image/png',
            'url_private': 'https://files.slack.com/files-pri/TTEST-FFIXTURE/fixture'}]}])
        adapter._has_active_session_for_thread = lambda **kw: False
    else:
        adapter._hydrate_thread_context = AsyncMock(return_value=('fixture prior context', [], []))
    real_build = adapter._build_message_event
    async def capture_build(*args, **kwargs):
        value = await real_build(*args, **kwargs)
        built.append(value)
        return value
    monkeypatch.setattr(adapter, '_build_message_event', capture_build)
    real_handler = runner._handle_message
    async def capture_native(event):
        native.append(event)
        assert get_hermes_home() == get_profile_dir(target)
        assert secret_scope.get_secret('TSK62_OWNER') == target
        assert secret_scope.get_secret('TSK62_AMBIENT_ONLY') is None
        assert (get_hermes_home() / 'owner.txt').read_text() == target
        return await real_handler(event)
    monkeypatch.setattr(runner, '_handle_message', capture_native)
    monkeypatch.setattr(runner, '_decide_image_input_mode', lambda **kw: 'native')
    async def model_boundary(**kwargs):
        model.append(kwargs)
        assert kwargs['source'].profile == target
        assert runner._adapter_for_source(kwargs['source']) is adapter
        assert get_hermes_home() == get_profile_dir(target)
        return {'final_response': 'fixture answer', 'messages': [], 'completed': True, 'api_calls': 1}
    monkeypatch.setattr(runner, '_run_agent', model_boundary)
    uid = config.registry.user_id_for(target)
    text = f'<@{uid}> inspect fixture' if kind != 'text' else f'{target}, inspect fixture'
    event = {'type': 'app_mention' if kind == 'mention' else 'message', 'channel': 'CEXEC',
             'channel_type': 'channel', 'user': 'UFIXTURE', 'ts': '1700000000.1', 'text': text}
    if kind == 'thread_image':
        event['thread_ts'] = '1700000000.1'
        event['ts'] = '1700000000.2'
    if kind in {'image', 'document'}:
        event['files'] = [{'id': 'FFIXTURE', 'name': 'fixture.txt' if kind == 'document' else 'fixture.png',
                           'size': 100, 'mimetype': 'text/plain' if kind == 'document' else 'image/png',
                           'url_private': 'https://files.slack.com/files-pri/TTEST-FFIXTURE/fixture'}]
    req = SocketModeRequest(type='events_api', envelope_id='env-fixture', payload={
        'type': 'event_callback', 'event_id': 'EvFixture', 'team_id': 'TTEST', 'event': event})
    acks = []
    async def ack(response):
        assert router.store.ack_journal.get('EvFixture')['wire_state'] == 'uncertain'
        acks.append(response.envelope_id)
    handler = adapter._make_socket_mode_handler()
    try:
        with _profile_runtime_scope(homes):
            await handler.handle(SimpleNamespace(send_socket_mode_response=ack, logger=logging.getLogger('fixture')), req)
            assert await adapter.drain_work_router_ingress()
            result = await router.process_once('EvFixture', sender=sender)
            await router.process_once('EvFixture', sender=sender)
        assert len(built) == 1, 'native admission rejected before Router'
        assert acks == ['env-fixture']
        assert router.store.ack_journal.get('EvFixture')['handoff_state'] == 'promoted'
        assert result.status == 'confirmed', result
        final_posts = [call for call in sdk.wire if call[1]['json'].get('text') == 'fixture answer']
        assert len(native) == len(model) == len(final_posts) == 1, [call[1]['json'] for call in sdk.wire]
        assert final_posts[0][1]['json']['channel'] == 'CEXEC'
        assert final_posts[0][1]['json']['thread_ts'] == '1700000000.1'
        assert final_posts[0][2] == []
        assert native[0].source.profile == target
        assert not native[0].allow_gateway_control
        assert all(auth == 'Bearer xoxb-recorded-receiver' and home == homes for _, auth, home in downloads)
        adapter.handle_message.assert_not_awaited()
        entry = runner.session_store.get_or_create_session(model[0]['source'])
        assert entry.session_id == model[0]['session_id']
        assert not getattr(adapter, '_work_router_native_contexts', {}), 'terminal work must release process-local media context'
        # This is the RED contract: enriched data built by native Slack must not disappear
        # merely because Router consumed the message. Never fix by unconditional ALLOW.
        if kind in {'image', 'document', 'thread_image'}:
            assert built[0].media_urls, 'fixture must exercise actual media enrichment'
            assert native[0].media_urls == built[0].media_urls, 'Router consumed but lost file/image context'
            assert native[0].media_types == built[0].media_types
        if kind == 'document':
            assert 'fixture-document-body' in native[0].text
        if kind in {'image', 'document', 'thread_image'}:
            assert sdk.file_checks and all(token == adapter.config.token and fid == 'FFIXTURE' for token, fid in sdk.file_checks)
            assert not adapter._work_router_native_contexts, 'terminal delivery must release enriched context'
    finally:
        await handler.close_async()
        router.store.close()
        if runner._session_db is not None:
            await runner._session_db.close()
