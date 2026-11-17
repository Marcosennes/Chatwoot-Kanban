import hashlib
import hmac
import logging

from fastapi import APIRouter, HTTPException, Request

from app.chatwoot_client import chatwoot_client
from app.config import settings
from app.database import get_pool, sync_task_from_chatwoot, write_audit_log
from app.routers.kanban import (
    PIPELINE_ATTR_KEY,
    _find_pipeline_attribute,
    _invalidate_board_cache,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_signature(payload: bytes, header: str | None) -> bool:
    if not settings.chatwoot_webhook_secret:
        return True
    if not header:
        return False
    expected = hmac.new(
        settings.chatwoot_webhook_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, header)


@router.post("/contact-updated")
async def contact_updated(request: Request):
    body = await request.body()
    sig = request.headers.get("x-chatwoot-signature")
    if not _verify_signature(body, sig):
        raise HTTPException(status_code=401, detail="invalid signature")

    data = await request.json()
    event_id = data.get("id")
    if not event_id:
        return {"status": "ignored", "reason": "missing event id"}

    pool = get_pool()
    existing = await pool.fetchrow(
        "SELECT id FROM webhook_events WHERE event_id = $1", event_id
    )
    if existing:
        return {"status": "duplicate", "event_id": event_id}

    contact = data.get("contact") or data.get("payload") or {}
    contact_id = contact.get("id")

    await pool.execute(
        """INSERT INTO webhook_events (event_id, contact_id, event_type, payload)
           VALUES ($1, $2, $3, $4)""",
        event_id,
        contact_id,
        data.get("event", "unknown"),
        body.decode(),
    )

    custom_attrs = contact.get("custom_attributes") or {}
    if contact_id and (
        custom_attrs.get("kanban_view_mensaje")
        or custom_attrs.get("kanban_view_fecha_termino")
    ):
        try:
            result = await sync_task_from_chatwoot(contact_id, custom_attrs)
            if result:
                logger.info("Webhook sync contact %s: %s", contact_id, result["action"])
        except Exception as exc:
            logger.error("Webhook sync failed for contact %s: %s", contact_id, exc)

    return {"status": "ok", "event_id": event_id}


@router.post("/conversation-updated")
async def conversation_updated(request: Request):
    body = await request.body()
    sig = request.headers.get("x-chatwoot-signature")
    if not _verify_signature(body, sig):
        raise HTTPException(status_code=401, detail="invalid signature")

    data = await request.json()
    event_id = data.get("id")
    if not event_id:
        return {"status": "ignored", "reason": "missing event id"}

    pool = get_pool()
    existing = await pool.fetchrow(
        "SELECT id FROM webhook_events WHERE event_id = $1", event_id
    )
    if existing:
        return {"status": "duplicate", "event_id": event_id}

    conversation = data.get("conversation") or {}
    conv_id = conversation.get("id")
    sender = (conversation.get("meta") or {}).get("sender") or {}
    contact_id = sender.get("id")

    await pool.execute(
        """INSERT INTO webhook_events
           (event_id, contact_id, conversation_id, event_type, payload)
           VALUES ($1, $2, $3, $4, $5)""",
        event_id,
        contact_id,
        conv_id,
        data.get("event", "unknown"),
        body.decode(),
    )

    return {"status": "ok", "event_id": event_id}


def _conversation_contact_id(conversation: dict) -> int | None:
    sender = (conversation.get("meta") or {}).get("sender") or {}
    if sender.get("id"):
        return sender["id"]
    return (conversation.get("contact_inbox") or {}).get("contact_id")


async def _read_webhook(request: Request) -> dict:
    body = await request.body()
    sig = request.headers.get("x-chatwoot-signature")
    if not _verify_signature(body, sig):
        raise HTTPException(status_code=401, detail="invalid signature")
    return await request.json()


async def _move_contact_stage(
    contact_id: int,
    conversation_id: int | None,
    *,
    target_index: int,
    only_from_index: int | None,
) -> dict:
    """Moves a contact to the pipeline stage at ``target_index``.

    Args:
        contact_id: Chatwoot contact id.
        conversation_id: Conversation that triggered the move, for auditing.
        target_index: Position of the destination stage in the pipeline.
        only_from_index: If set, only contacts currently in this stage move.
            If None, only contacts without a stage move.

    Returns:
        Webhook response body describing what happened.
    """
    try:
        definitions = await chatwoot_client.get_custom_attribute_definitions()
        pipeline_attr = _find_pipeline_attribute(definitions)
        stages = pipeline_attr.get("attribute_values", []) if pipeline_attr else []
        if len(stages) <= target_index:
            return {"status": "ignored", "reason": "pipeline stage not configured"}

        contact = await chatwoot_client.get_contact(contact_id)
        contact_data = contact.get("payload", contact)
        custom_attrs = contact_data.get("custom_attributes") or {}
        current = custom_attrs.get(PIPELINE_ATTR_KEY)
        expected = stages[only_from_index] if only_from_index is not None else None
        if (current or None) != expected:
            return {"status": "ignored", "reason": "contact not in source stage"}

        target = stages[target_index]
        await chatwoot_client.update_contact_custom_attributes(
            contact_id, {**custom_attrs, PIPELINE_ATTR_KEY: target}
        )
    except Exception as exc:
        logger.error("Auto-stage failed for contact %s: %s", contact_id, exc)
        raise HTTPException(status_code=502, detail="chatwoot api error") from exc

    _invalidate_board_cache()
    try:
        await write_audit_log(
            contact_id=contact_id,
            conversation_id=conversation_id,
            actor_agent_id=0,
            actor_name="webhook",
            action="stage_change",
            previous_state={"stage_from": current},
            new_state={"stage_to": target},
            source="webhook",
            chatwoot_call_ok=True,
        )
    except Exception as exc:
        logger.warning("Audit log failed for contact %s: %s", contact_id, exc)

    logger.info("Contact %s auto-moved %r -> %r", contact_id, current, target)
    return {"status": "ok", "contact_id": contact_id, "stage": target}


@router.post("/conversation-created")
async def conversation_created(request: Request):
    """Places the contact of a new conversation in the first pipeline stage.

    Contacts that already have a stage are left untouched.
    """
    data = await _read_webhook(request)
    if data.get("event") != "conversation_created":
        return {"status": "ignored", "reason": "unsupported event"}

    contact_id = _conversation_contact_id(data)
    if not contact_id:
        return {"status": "ignored", "reason": "missing contact id"}

    return await _move_contact_stage(
        contact_id, data.get("id"), target_index=0, only_from_index=None
    )


@router.post("/message-created")
async def message_created(request: Request):
    """Moves a contact from the first to the second stage on an agent reply.

    Only public outgoing messages written by a human agent count; private
    notes, bot messages and automated replies are ignored.
    """
    data = await _read_webhook(request)
    if data.get("event") != "message_created":
        return {"status": "ignored", "reason": "unsupported event"}

    sender = data.get("sender") or {}
    is_agent_reply = (
        data.get("message_type") == "outgoing"
        and not data.get("private")
        and sender.get("type") == "user"
    )
    if not is_agent_reply:
        return {"status": "ignored", "reason": "not an agent reply"}

    conversation = data.get("conversation") or {}
    contact_id = _conversation_contact_id(conversation)
    if not contact_id:
        return {"status": "ignored", "reason": "missing contact id"}

    return await _move_contact_stage(
        contact_id, conversation.get("id"), target_index=1, only_from_index=0
    )
