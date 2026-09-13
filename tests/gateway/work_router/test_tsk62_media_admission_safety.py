"""Fail closed at the real Bolt/journal boundary, without retaining attachment data."""
from unittest.mock import AsyncMock

import httpx
import pytest

from gateway.work_router.service import WorkRouter
from tests.gateway.work_router.test_tsk62_preack_journal import (
    adapter_for, deliver, request, router,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("synchronous", [False, True])
@pytest.mark.parametrize("kind", ["image", "document", "thread_image", "download_denied", "missing_url"])
async def test_media_cannot_be_confirmed_as_text_even_after_reopen(
    router, tmp_path, monkeypatch, caplog, synchronous, kind,
):
    from tools import url_safety
    from tests.gateway.work_router.test_tsk62_media_profile_closure import PNG

    adapter = adapter_for(router, synchronous=synchronous)
    downloads = []
    def download(req):
        downloads.append(req)
        if kind == "download_denied":
            return httpx.Response(403)
        return httpx.Response(200, content=b"private-document-body" if kind == "document" else PNG,
                              headers={"content-type": "text/plain" if kind == "document" else "image/png"})
    monkeypatch.setattr(url_safety, "is_safe_url", lambda url: True)
    monkeypatch.setattr(url_safety, "create_ssrf_safe_async_client",
                        lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(download), **kw))
    extra = {}
    if kind == "thread_image":
        root = tmp_path / "private-root.png"
        root.write_bytes(PNG)
        adapter._hydrate_thread_context = AsyncMock(return_value=("prior thread context", [str(root)], ["image/png"]))
        extra["thread_ts"] = "1700000000.0"
    else:
        extra["files"] = [{"id": "FPRIVATE", "name": "private.txt" if kind == "document" else "private.png",
                           "mimetype": "text/plain" if kind == "document" else "image/png", "size": 100}]
        if kind != "missing_url":
            extra["files"][0]["url_private"] = "https://files.slack.com/files-pri/TTEST-FPRIVATE/private"
    built = []
    original = adapter._build_message_event
    async def capture(*args, **kwargs):
        native = await original(*args, **kwargs)
        built.append(native)
        # Actual unavailable native cache, not blanket rejection of valid media.
        if kind in {'image', 'document'}:
            from pathlib import Path
            for path in native.media_urls:
                Path(path).unlink()
        return native
    monkeypatch.setattr(adapter, "_build_message_event", capture)
    wire = AsyncMock()
    req = request(**extra)
    await deliver(adapter, req, wire)
    assert len(built) == 1
    if kind in {"image", "document", "thread_image"}:
        assert built[0].media_urls
    if kind == "document":
        assert "private-document-body" in built[0].text
    row = router.store.ack_journal.get("EvReceipt")
    assert row["native_state"] == "rejected", "media-losing path must not be admitted as text"
    assert row["reason"] == "media_context_unavailable"
    assert row["wire_state"] == "confirmed"
    assert row["handoff_state"] == "pending"
    assert row["payload_json"] is None
    assert router.store.get_event("EvReceipt") is None
    assert "media_context_unavailable" in caplog.text
    adapter.handle_message.assert_not_awaited()
    wire.assert_awaited_once()

    # A fresh store/adapter must not manufacture an executable text-only event.
    recovered = WorkRouter(router.config)
    try:
        fresh = adapter_for(recovered, synchronous=synchronous)
        await fresh.recover_work_router_ingress()
        await deliver(fresh, req, wire)
        assert recovered.store.ack_journal.get("EvReceipt")["reason"] == "media_context_unavailable"
        assert recovered.store.ack_journal.ready() == []
        assert recovered.store.inbox_count() == 0
        sender = AsyncMock()
        result = await recovered.process_once("EvReceipt", sender=sender)
        assert result.status == "missing"
        sender.assert_not_awaited()
        fresh.handle_message.assert_not_awaited()
        fresh._hydrate_thread_context.assert_not_awaited()
        wire.assert_awaited_once()
        for record in recovered.store._conn.execute("SELECT payload_json, reason FROM router_ack_receipts"):
            assert "private-document-body" not in str(tuple(record))
            assert "files.slack.com" not in str(tuple(record))
    finally:
        recovered.store.close()
