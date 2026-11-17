# 020: Entrada en el sidebar de Chatwoot, acceso a conversación y notificaciones

- **Fecha:** 2026-11-17
- **Estado:** Aceptado
- **Autor(es):** Marcosennes

## Contexto

El tablero solo era accesible como Dashboard App (pestaña dentro de una
conversación, ADR-001) o por URL directa. Los agentes querían abrirlo desde
el menú principal, saltar de una tarjeta a la conversación del cliente y ver
mensajes nuevos sin salir del tablero.

Chatwoot no ofrece un punto de extensión para el sidebar, pero sí la
configuración de instalación `DASHBOARD_SCRIPTS`, que inyecta HTML al final
del `<body>` del panel de agentes.

## Decisión

1. **Script de sidebar** (`app/static/chatwoot-sidebar.js`, servido en
   `/chatwoot-sidebar.js`) cargado vía `DASHBOARD_SCRIPTS`. Clona el primer
   ítem nativo del menú (`aside nav > ul > li`) para heredar estilos, lo
   reinserta con un `MutationObserver` cuando Vue re-renderiza y muestra el
   tablero en un panel fijo a la derecha del sidebar.
2. **Botón "Abrir conversa" en la tarjeta**: `GET
   /kanban/contacts/{id}/conversation` resuelve la conversación más reciente
   bajo demanda (no se agrega al payload del board). Dentro del panel, el
   iframe pide la navegación por `postMessage` (`kanban:navigate`) y el
   script usa el router de Vue de Chatwoot; sin respuesta en 400 ms se abre
   una pestaña nueva.
3. **Campanita de notificaciones**: `GET /kanban/notifications` lista las
   conversaciones cuyo último mensaje es del cliente. El estado leído/no
   leído es el `unread_count` de Chatwoot, de modo que abrir la conversación
   en Chatwoot la marca como leída. Polling cada 10 s.

## Consecuencias

- **Positivas:** acceso al tablero desde el menú principal; sin tablas ni
  estado nuevo en la BD del plugin para notificaciones.
- **Negativas:** el script depende de la estructura DOM del sidebar y del
  `__vue_app__` de Chatwoot; una actualización puede romperlo (falla en
  silencio: el ítem simplemente no aparece).
- **Riesgos:** `unread_count` es por conversación, no por agente. El conteo
  usa solo la primera página (25) de conversaciones. La URL del script en
  `DASHBOARD_SCRIPTS` debe ser la URL pública del plugin en producción.

## Alternativas consideradas

| Opción | Pros | Contras | ¿Por qué no? |
| ------ | ---- | ------- | ------------ |
| Fork del frontend de Chatwoot | Integración nativa | Mantener un fork de Chatwoot | Costo de mantenimiento |
| Tabla propia de notificaciones vía webhook | Leído por agente | Estado duplicado, más código | Sobredimensionado para el caso |
| Incluir conversation_id en el board | Un clic sin espera | Una llamada extra por contacto en cada carga | Penaliza el board |
