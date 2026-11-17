# 019: Automatizaciones de etapa por webhook

- **Fecha:** 2026-11-17
- **Estado:** Aceptado
- **Autor(es):** Marcosennes

## Contexto

Hasta ahora un contacto solo aparecía en el tablero cuando un agente le
asignaba manualmente una etapa (`pipeline_01_etapas`). Los contactos nuevos
quedaban fuera del Kanban y el avance inicial del embudo dependía de que el
agente recordara mover la tarjeta.

Las reglas de automatización nativas de Chatwoot no permiten escribir
custom attributes de contacto, así que la automatización tiene que vivir en
el plugin.

## Decisión

Agregar dos receptores de webhook que mueven la etapa del contacto en
Chatwoot (fuente de verdad, ver ADR-006):

| Evento Chatwoot        | Endpoint                          | Regla                                   |
| ---------------------- | --------------------------------- | --------------------------------------- |
| `conversation_created` | `/webhooks/conversation-created`  | Sin etapa → primera etapa del pipeline  |
| `message_created`      | `/webhooks/message-created`       | Respuesta de agente: 1ª etapa → 2ª etapa |

- Las reglas usan la **posición** de la etapa en `attribute_values`, no el
  nombre, para sobrevivir a renombres.
- Solo avanzan; nunca retroceden un contacto que ya está más adelante.
- "Respuesta de agente" = mensaje `outgoing`, no privado, con
  `sender.type == "user"`. Notas privadas, bots y mensajes del cliente se
  ignoran.
- Cada movimiento invalida el cache del board y queda en `task_audit_log`
  con `source="webhook"`.
- La lógica comparte el helper `_move_contact_stage`.

## Consecuencias

- **Positivas:** todo contacto con conversación aparece en el tablero; el
  paso Nuevo → En curso es automático.
- **Negativas:** dos webhooks más que configurar en Chatwoot;
  `message_created` llega por cada mensaje (los no relevantes se descartan
  sin llamar a la API).
- **Riesgos:** Chatwoot ≥ 4.x bloquea webhooks a IPs privadas (SSRF). En
  despliegues donde Chatwoot y el plugin comparten red Docker hay que usar
  una URL pública o `SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true` en Chatwoot.
  La verificación de firma sigue el formato existente (`x-chatwoot-signature`)
  y no se validó contra el formato de firma de Chatwoot 4.x.

## Alternativas consideradas

| Opción | Pros | Contras | ¿Por qué no? |
| ------ | ---- | ------- | ------------ |
| Automation rules de Chatwoot | Sin código | No escriben custom attributes de contacto | No resuelve el caso |
| Polling desde el cron | Sin webhooks | Latencia, más llamadas a la API | El tablero debe reaccionar en segundos |
| Reglas por nombre de etapa | Explícito | Se rompe al renombrar etapas | Frágil |
