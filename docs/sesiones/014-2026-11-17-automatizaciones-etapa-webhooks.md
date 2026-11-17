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
5. **Ítem "Kanban" en el sidebar de Chatwoot** vía `DASHBOARD_SCRIPTS`
   (`/chatwoot-sidebar.js`), con el tablero en un panel junto al menú.
6. **Botón "Abrir conversa" en la tarjeta** (`GET
   /kanban/contacts/{id}/conversation`), navegando con el router de Chatwoot
   cuando el tablero está dentro del panel.
7. **Campanita de notificaciones** en el header del tablero (`GET
   /kanban/notifications`), con badge de no leídas basado en `unread_count`.
   Decisiones 5–7 documentadas en ADR-020.
8. Tests: 11 nuevos (43 en total), Ruff limpio.

## Verificación

Chatwoot 4.19.1-ce local en la red `chatwoot_shared`, widget web de prueba:

- Conversación nueva desde el widget → contacto aparece en la 1ª columna.
- Respuesta de agente vía API → tarjeta pasa a la 2ª columna.
- Mensaje nuevo de cliente → aparece como no leído en `/kanban/notifications`.
- `DASHBOARD_SCRIPTS` inyectado en el HTML del panel de Chatwoot. El ítem del
  sidebar y la navegación no se verificaron con navegador automatizado.

## Notas de entorno

- Chatwoot 4.x bloquea webhooks a IPs privadas; en local se habilitó
  `SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true` en el `.env` de Chatwoot.
- Docker instalado vía snap (AppArmor) rechaza `no-new-privileges`; se usa
  un `docker-compose.override.yml` local, no versionado.

## Siguiente paso

- Validar la firma HMAC de Chatwoot 4.x y habilitar
  `CHATWOOT_WEBHOOK_SECRET`.
- Evaluar hacer configurables las reglas (etapa origen/destino) vía env.
- Configurar `DASHBOARD_SCRIPTS` con la URL pública del plugin en producción.
