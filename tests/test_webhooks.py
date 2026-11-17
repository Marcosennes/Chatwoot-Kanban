from unittest.mock import AsyncMock, patch

from tests.conftest import _sign


def test_webhook_contact_updated_valid_signature(client):
    body = (
        b'{"id": "evt-101", "event": "contact_updated",'
        b' "contact": {"id": 50, "custom_attributes": {}}}'
    )
    sig = _sign(body, "test-secret")

    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value=None)
    mock_pool.execute = AsyncMock()

    with patch("app.routers.webhooks.get_pool", return_value=mock_pool):
        response = client.post(
            "/webhooks/contact-updated",
            content=body,
            headers={
                "x-chatwoot-signature": sig,
                "content-type": "application/json",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_webhook_contact_updated_invalid_signature(client):
    body = b'{"id": "evt-102", "event": "contact_updated"}'

    response = client.post(
        "/webhooks/contact-updated",
        content=body,
        headers={
            "x-chatwoot-signature": "invalid-sig",
            "content-type": "application/json",
        },
    )
    assert response.status_code == 401


def test_webhook_contact_updated_missing_event_id(client):
    body = b'{"event": "contact_updated", "contact": {"id": 50}}'
    sig = _sign(body, "test-secret")

    response = client.post(
        "/webhooks/contact-updated",
        content=body,
        headers={
            "x-chatwoot-signature": sig,
            "content-type": "application/json",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_webhook_contact_updated_duplicate(client):
    body = (
        b'{"id": "evt-103", "event": "contact_updated",'
        b' "contact": {"id": 50, "custom_attributes": {}}}'
    )
    sig = _sign(body, "test-secret")

    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value={"id": 1})

    with patch("app.routers.webhooks.get_pool", return_value=mock_pool):
        response = client.post(
            "/webhooks/contact-updated",
            content=body,
            headers={
                "x-chatwoot-signature": sig,
                "content-type": "application/json",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "duplicate"


def test_webhook_conversation_updated_valid_signature(client):
    body = (
        b'{"id": "evt-001", "event": "conversation_updated",'
        b' "conversation": {"id": 1, "meta": {"sender": {"id": 50}}}}'
    )
    sig = _sign(body, "test-secret")

    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value=None)
    mock_pool.execute = AsyncMock()

    with patch("app.routers.webhooks.get_pool", return_value=mock_pool):
        response = client.post(
            "/webhooks/conversation-updated",
            content=body,
            headers={
                "x-chatwoot-signature": sig,
                "content-type": "application/json",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_webhook_conversation_updated_invalid_signature(client):
    body = b'{"id": "evt-002", "event": "conversation_updated"}'

    response = client.post(
        "/webhooks/conversation-updated",
        content=body,
        headers={
            "x-chatwoot-signature": "invalid-sig",
            "content-type": "application/json",
        },
    )
    assert response.status_code == 401


CONVERSATION_CREATED = (
    b'{"event": "conversation_created", "id": 3, "meta": {"sender": {"id": 7}}}'
)


def _post_conversation_created(client, payload: bytes):
    return client.post(
        "/webhooks/conversation-created",
        content=payload,
        headers={
            "x-chatwoot-signature": _sign(payload, "test-secret"),
            "content-type": "application/json",
        },
    )


def _mock_chatwoot(contact_attrs: dict):
    from tests.conftest import MOCK_ATTRIBUTE_DEFINITIONS

    mock = AsyncMock()
    mock.get_custom_attribute_definitions = AsyncMock(
        return_value=MOCK_ATTRIBUTE_DEFINITIONS
    )
    mock.get_contact = AsyncMock(
        return_value={"payload": {"id": 7, "custom_attributes": contact_attrs}}
    )
    mock.update_contact_custom_attributes = AsyncMock()
    return mock


def test_conversation_created_sets_first_stage(client):
    payload = CONVERSATION_CREATED
    mock = _mock_chatwoot({"other": "x"})

    with (
        patch("app.routers.webhooks.chatwoot_client", mock),
        patch("app.routers.webhooks.write_audit_log", new_callable=AsyncMock),
    ):
        response = _post_conversation_created(client, payload)

    assert response.status_code == 200
    assert response.json()["stage"] == "Potencial"
    mock.update_contact_custom_attributes.assert_awaited_once_with(
        7, {"other": "x", "pipeline_01_etapas": "Potencial"}
    )


def test_conversation_created_keeps_existing_stage(client):
    payload = CONVERSATION_CREATED
    mock = _mock_chatwoot({"pipeline_01_etapas": "Cerrado"})

    with patch("app.routers.webhooks.chatwoot_client", mock):
        response = _post_conversation_created(client, payload)

    assert response.json()["status"] == "ignored"
    mock.update_contact_custom_attributes.assert_not_awaited()


def test_conversation_created_ignores_other_events(client):
    payload = b'{"event": "message_created", "id": 3}'

    response = _post_conversation_created(client, payload)

    assert response.json()["status"] == "ignored"


AGENT_REPLY = (
    b'{"event": "message_created", "message_type": "outgoing", "private": false,'
    b' "sender": {"id": 1, "type": "user"},'
    b' "conversation": {"id": 3, "contact_inbox": {"contact_id": 7}}}'
)


def _post_message_created(client, payload: bytes):
    return client.post(
        "/webhooks/message-created",
        content=payload,
        headers={
            "x-chatwoot-signature": _sign(payload, "test-secret"),
            "content-type": "application/json",
        },
    )


def test_agent_reply_moves_first_stage_to_second(client):
    mock = _mock_chatwoot({"pipeline_01_etapas": "Potencial"})

    with (
        patch("app.routers.webhooks.chatwoot_client", mock),
        patch("app.routers.webhooks.write_audit_log", new_callable=AsyncMock),
    ):
        response = _post_message_created(client, AGENT_REPLY)

    assert response.json()["stage"] == "En evaluación"
    mock.update_contact_custom_attributes.assert_awaited_once_with(
        7, {"pipeline_01_etapas": "En evaluación"}
    )


def test_agent_reply_keeps_later_stage(client):
    mock = _mock_chatwoot({"pipeline_01_etapas": "Cerrado"})

    with patch("app.routers.webhooks.chatwoot_client", mock):
        response = _post_message_created(client, AGENT_REPLY)

    assert response.json()["status"] == "ignored"
    mock.update_contact_custom_attributes.assert_not_awaited()


def test_incoming_and_private_messages_are_ignored(client):
    incoming = AGENT_REPLY.replace(b'"outgoing"', b'"incoming"')
    private_note = AGENT_REPLY.replace(b'"private": false', b'"private": true')

    for payload in (incoming, private_note):
        assert _post_message_created(client, payload).json()["status"] == "ignored"
