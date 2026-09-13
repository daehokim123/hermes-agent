"""Rare, privacy-safe approval delivery correlation (never log prompt bodies)."""
import json
import logging


def log_approval_delivery(logger: logging.Logger, event: str, *, request_id,
                          session_id='', success=None):
    record: dict[str, object] = {'event': event, 'request_id': str(request_id or ''),
              'session_id': str(session_id or '')}
    if success is not None:
        record['success'] = bool(success)
    # Operational gateways default to WARNING; these rare records must survive.
    logger.warning('approval_delivery_trace %s', json.dumps(record, sort_keys=True))
