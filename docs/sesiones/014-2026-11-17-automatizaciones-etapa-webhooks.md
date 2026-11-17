# Sesión 014 — Automatizaciones de etapa por webhook

| Campo | Valor |
|---|---|
| **Fecha** | 2026-11-17 |
| **Tipo** | Feature / Integración |
| **Proyecto** | chatwoot-kanban (fork Marcosennes) |
| **Estado al cierre** | Automatizaciones verificadas end-to-end contra Chatwoot 4.19.1 local |

---

## Objetivo de la sesión

Levantar el fork con Docker junto a un Chatwoot local y automatizar el
movimiento de tarjetas: contacto nuevo entra al tablero y la respuesta de un
agente lo pasa a la siguiente etapa.

## Qué se hizo

1. **Redirect `/` → `/kanban`** (`app/main.py`): la raíz devolvía 404.
2. **`POST /webhooks/conversation-created`**: contacto sin etapa → primera
   etapa del pipeline.
3. **`POST /webhooks/message-created`**: respuesta pública de agente mueve
   de la 1ª a la 2ª etapa; nunca retrocede.
4. Helper común `_move_contact_stage` con audit log (`source="webhook"`) e
   invalidación de cache. Decisión documentada en ADR-019.
5. Tests: 6 nuevos (38 en total), Ruff limpio.

## Verificación

Chatwoot 4.19.1-ce local en la red `chatwoot_shared`, widget web de prueba:

- Conversación nueva desde el widget → contacto aparece en la 1ª columna.
- Respuesta de agente vía API → tarjeta pasa a la 2ª columna.

## Notas de entorno

- Chatwoot 4.x bloquea webhooks a IPs privadas; en local se habilitó
  `SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true` en el `.env` de Chatwoot.
- Docker instalado vía snap (AppArmor) rechaza `no-new-privileges`; se usa
  un `docker-compose.override.yml` local, no versionado.

## Siguiente paso

- Validar la firma HMAC de Chatwoot 4.x y habilitar
  `CHATWOOT_WEBHOOK_SECRET`.
- Evaluar hacer configurables las reglas (etapa origen/destino) vía env.
