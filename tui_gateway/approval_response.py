"""Approval response forwarding over the native compute-host prompt transport."""
from approval_trace import log_approval_delivery


def respond_via_host(rid, params, session):
    from tui_gateway import server
    # The live sid may have been recovered via the stored-id fallback.
    with server._sessions_lock:
        sid = next((sid for sid, value in server._sessions.items() if value is session), None)
    if sid is None:
        return server._err(rid, 4001, 'session not found')
    try:
        ack = server._get_compute_host_supervisor().respond(
            sid, params, method='approval.respond')
    except Exception:
        log_approval_delivery(server.logger, 'APPROVAL_HOST_RESPONSE',
                              request_id=params.get('request_id'), session_id=sid, success=False)
        return server._err(rid, 5019, 'compute-host approval response failed')
    response = ack.get('response')
    if not isinstance(response, dict) or ack.get('type') != 'respond.ack':
        return server._err(rid, 5019, 'invalid compute-host approval response')
    log_approval_delivery(server.logger, 'APPROVAL_HOST_RESPONSE',
                          request_id=params.get('request_id'), session_id=sid,
                          success=(response.get('result') or {}).get('resolved', 0) > 0)
    return {**response, 'id': rid}
