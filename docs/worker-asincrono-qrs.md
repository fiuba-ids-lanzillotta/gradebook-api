# Worker asincrónico para envío de emails (`gradebook-mailer`)

Contexto y decisiones del worker que desacopla del request HTTP el envío de **todos**
los emails de la plataforma (QRs de asistencia, confirmación de asistencia, bienvenida
a docentes y recuperación de contraseña). Ya está implementado y deployado.

Repo del worker: `gradebook-mailer` (app Flask separada, deployada en Vercel).

**Dónde está el resto de la info** (este doc ya no duplica contrato ni operación):

- Endpoints, payloads y semántica de respuestas del worker: `docs/swagger.yaml` y
  `README.md` del repo `gradebook-mailer`.
- Flujos end-to-end (sequence/state/component diagrams): [flujos.md](flujos.md).
- Variables de entorno de cada lado: `.env.example` de cada repo y la tabla del README
  del API.
- Checklist de deploy: skill `deploy-vercel` del repo del worker.

## Motivación

El endpoint `/clases/{id}/enviar-qrs` enviaba los emails dentro del mismo request HTTP.
Funciona para clases pequeñas, pero genera problemas con muchos estudiantes:

- **Gmail throttling**: puede cerrar la conexión SMTP (`Broken pipe`) si se envían
  demasiados emails seguidos.
- **Vercel Hobby timeout**: el request se corta a los 10 segundos.
- **Conexiones inactivas**: mientras el SMTP está bloqueado, la conexión HTTP/2 con
  Supabase puede volverse stale y romperse al registrar el envío.
- **El front era el scheduler**: el envío avanzaba solo mientras el docente tuviera la
  pestaña abierta haciendo polling a `/enviar-qrs`.

## Arquitectura

```
front → gradebook-api → Upstash QStash → gradebook-mailer → Supabase + SMTP
                ↑                                            (Vercel)
                └── GET /clases/{id}/envio (polling de progreso, sin cambios)
```

La API publica en QStash; QStash entrega al worker con firma `Upstash-Signature`; el
worker envía por SMTP y registra el estado del envío en `asistencias` (para los QRs).
Diagrama completo en [flujos.md](flujos.md).

## Decisiones tomadas

- **Cola**: Upstash QStash. El worker es serverless en Vercel.
- **Discriminación por endpoint**: un endpoint del worker por tipo de email (no un
  campo `evento` en el payload).
- **Migran los 4 emails**: QR, confirmación de asistencia, bienvenida y recuperación.
- **Secretos en el payload**: la password temporal y el link de reset viajan en el
  mensaje de QStash (TLS en tránsito; quedan en Upstash hasta la entrega). Se acepta
  el riesgo: el token expira rápido y la password es temporal.
- **Fan-out con ids**: la API publica N mensajes `{clase_id, asistencia_ids}` en una
  sola llamada `/v2/batch`. Cada mensaje "posee" sus filas: idempotente y sin
  solapamiento entre entregas concurrentes. El lote de ~5 por mensaje entra cómodo en
  el presupuesto de ejecución serverless.
- **Respuesta del worker**: `200` aunque emails individuales fallen (se registran en
  `envio_intentos`/`envio_error`, reencolables con `reintentar=true`). `5xx` solo ante
  fallas de infraestructura, para que QStash reintente.
- **Publish fallido → fail-open**: se loguea y se sigue. Los QRs quedan pendientes y el
  front los reintenta; los transaccionales tienen el mismo comportamiento fail-safe de
  antes. Sin fallback sincrónico en prod (reintroduciría el timeout).
- **Dev/tests**: sin `QSTASH_TOKEN`/`MAIL_WORKER_URL`, `cola.publicar` loguea el
  payload completo (incluidos link de reset y password temporal) y `enviar_qrs` hace
  dry-run: loguea código+destinatario y marca la asistencia enviada para que el polling
  del front complete. **La API no envía emails**: `mailer.py` y los templates viven
  solo en el worker.
- **Código duplicado**: `mailer.py`, templates y helpers viven solo en el worker (no se
  publica librería a PyPI ni paquete git compartido: poco código, cambia poco, y el
  overhead de packaging no se justifica con solo 2 consumidores).
- **Sin SDK en la API**: publicar es un POST HTTPS común con `requests` (ya era
  dependencia). El SDK `qstash` solo lo usa el worker, para verificar firmas con
  `qstash.Receiver` — la parte donde conviene la implementación oficial.

## Dónde se publica desde la API

`gradebook_api/cola.py` (`publicar` → `/v2/publish`, `publicar_lote` → `/v2/batch`),
env-gated y fail-open. Los 4 puntos de disparo:

- `services/asistencias.py::enviar_qrs` → `/emails/qr-lote` (batch, fan-out de a 5).
- `services/asistencias.py::marcar_asistencia` → `/emails/confirmacion` (solo la
  primera vez que la asistencia pasa a `presente`).
- `services/docentes.py::crear_docente` → `/emails/bienvenida`.
- `services/password_reset.py::solicitar_recuperacion` → `/emails/recuperacion`.

## Riesgos y límites conocidos

- **El timeout de Vercel sigue aplicando al worker** por ejecución: por eso lotes de
  ~5 y per-email error → 200 (un email lento no arrastra al resto del lote).
- **QStash no acelera Gmail**: los límites del SMTP (~500 destinatarios/día en cuentas
  gratuitas) siguen igual; el worker solo distribuye el envío en el tiempo.
- **QStash es at-least-once**: un QR puede enviarse dos veces si el worker muere entre
  el `send()` y el update de `enviado`. Mitigado re-chequeando `enviado` antes de cada
  send; el duplicado residual es inofensivo (mismo código). Para la confirmación no hay
  flag de "enviado": un reintento raro puede mandar el email dos veces (se acepta).
- **Límite free de QStash** (~500 mensajes/día): una clase de 200 con lotes de 5 son
  40 mensajes + ~200 confirmaciones si se marca por QR. Vigilar el uso; QStash tiene
  DLQ para los mensajes que agotan reintentos.
- **Duplicación de código** (mailer, templates, db de asistencias): es el costo del
  repo separado; mantener a la par con la API.
- **Cold starts**: el primer mensaje paga el arranque dentro del presupuesto.
- **Opcional, no implementado**: `Upstash-Delay` por mensaje o Flow Control (key por
  `clase_id`) para espaciar las entregas y no castigar Gmail.
