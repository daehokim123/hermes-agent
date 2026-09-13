"""Real approval registry + JSON-RPC/host response round trips; no commands execute."""
import io
import json
import logging
import threading

import pytest
from tools import approval
from tools.approval_gateway_wait import _ApprovalEntry
from tui_gateway import server
from tui_gateway.compute_host import ComputeHost

@pytest.mark.parametrize('hosted', [False, True])
def test_exact_approval_resolution_and_safe_trace(monkeypatch, caplog, hosted):
    sid, key = 'approval-live', 'approval-stored'
    first = _ApprovalEntry({'command':'SECRET_COMMAND', 'description':'SECRET_DESCRIPTION'})
    second = _ApprovalEntry({'command':'SECOND_SECRET', 'description':'SECRET_DESCRIPTION'})
    monkeypatch.setitem(server._sessions, sid, {'session_key':key, 'history_lock':threading.Lock()})
    monkeypatch.setitem(approval._gateway_queues, key, [first, second])
    params = {'session_id':sid, 'request_id':second.data['request_id'], 'choice':'deny'}
    caplog.set_level(logging.WARNING)
    if hosted:
        out = io.StringIO()
        host = ComputeHost(stdout=out, heartbeat_secs=0)
        try:
            host._handle_respond({'sid':sid, 'request_id':'transport-id', 'method':'approval.respond', 'params':params})
            response = json.loads(out.getvalue().splitlines()[-1])['response']
        finally:
            host.close()
    else:
        response = server.handle_request({'id':'rpc-id', 'method':'approval.respond', 'params':params})
    assert response['result']['resolved'] == 1
    assert second.event.is_set() and not first.event.is_set()
    assert server.handle_request({'id':'stale','method':'approval.respond','params':params})['result']['resolved'] == 0
    traces = [r.getMessage() for r in caplog.records if 'approval_delivery_trace' in r.getMessage()]
    assert traces and any(second.data['request_id'] in message for message in traces)
    assert all('SECRET' not in message for message in traces)


def test_parent_native_transport_routes_to_host_and_traces_delivery(monkeypatch, caplog, tmp_path):
    from tui_gateway.host_supervisor import HostSupervisor
    sid, key = 'host-approval-live', 'host-approval-stored'
    pending = _ApprovalEntry({'command':'SECRET_COMMAND', 'description':'SECRET_DESCRIPTION'})
    monkeypatch.setitem(server._sessions, sid, {'session_key':key, 'history_lock':threading.Lock()})
    monkeypatch.setitem(approval._gateway_queues, key, [pending])
    supervisor = HostSupervisor(cwd=tmp_path)
    monkeypatch.setattr(supervisor, 'start', lambda: None)
    monkeypatch.setattr(server, '_get_compute_host_supervisor', lambda: supervisor)
    monkeypatch.setattr(server, '_session_uses_compute_host', lambda session: True)
    out = io.StringIO()
    host = ComputeHost(stdout=out, heartbeat_secs=0)
    sent = []
    def wire(frame):
        sent.append(json.loads(json.dumps(frame)))
        with monkeypatch.context() as child:
            child.setattr(server, '_session_uses_compute_host', lambda session: False)
            host._handle_respond(sent[-1])
        reply = json.loads(out.getvalue().splitlines()[-1])
        supervisor._deliver_control_frame(reply['request_id'], reply)
    monkeypatch.setattr(supervisor, '_send_frame', wire)
    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(server, 'write_json', lambda message: True)
    event = {'method':'event', 'params':{'type':'approval.request', 'session_id':sid, 'payload':pending.data}}
    assert server._relay_compute_host_rpc(event)
    try:
        response = server.handle_request({'id':'parent-rpc', 'method':'approval.respond', 'params':{
            'session_id':sid, 'request_id':pending.data['request_id'], 'choice':'deny'}})
        assert response['id'] == 'parent-rpc'
        assert response['result']['resolved'] == 1
        assert pending.event.is_set()
        assert sent[0]['request_id'] != pending.data['request_id']
        assert sent[0]['params']['request_id'] == pending.data['request_id']
        traces = [r.getMessage() for r in caplog.records if 'approval_delivery_trace' in r.getMessage()]
        assert any('APPROVAL_HOST_RELAY' in text for text in traces)
        assert any('APPROVAL_HOST_RESPONSE' in text for text in traces)
        assert all('SECRET' not in text for text in traces)
    finally:
        host.close()
