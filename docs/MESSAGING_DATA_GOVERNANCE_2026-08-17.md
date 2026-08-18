# SOAiaCore · Messaging & Data Governance

Fecha: 2026-08-17

## Scope
Aplica a WhatsApp, Telegram, Instagram, OCR, imágenes, audio, video, logs, embeddings y análisis con modelos.

## Default state
`OBSERVE_ONLY=true`

No se habilita envío automático.

## Approval gates

### Gate A · análisis
Evento entrante → metadata mínima → `PENDING_ANALYSIS_APPROVAL`.

Sólo tras aprobación humana puede pasar a `ANALYZED` cuando el contenido sea sensible o el canal esté marcado como privado.

### Gate B · envío/publicación
Borrador → `PENDING_SEND_APPROVAL` → acción humana explícita → `SENT`.

No existe transición automática entre borrador y envío.

## Retención

Clasificación inicial:
- `EPHEMERAL`: basura operacional / duplicados / artefactos temporales.
- `CONTEXTUAL`: necesario para correlación limitada.
- `ARCHIVAL`: seleccionado conscientemente para conservación.
- `RESTRICTED`: sexual, clínica, financiera, autenticación, localización precisa o material de terceros de alta sensibilidad.

Reglas:
- La clasificación RESTRICTED no implica conservar; implica controles superiores.
- Deduplicar medios por hash antes de copiar.
- Mantener metadata y extractos sólo cuando reduzcan la necesidad de conservar el binario original.
- Backups externos de RESTRICTED deben cifrarse antes de subir.

## Logs

Permitido:
- event_id
- timestamp
- channel
- message/content hash
- classification
- model/request id
- latency
- status/error code

No permitido por defecto:
- texto completo de chats
- tokens OAuth/API
- cookies/sesiones
- imágenes completas
- query strings con secretos

## OpenAI

- API keys sólo en backend.
- `store=false` por defecto cuando no se requiera almacenamiento de estado de la Responses API.
- Evaluar Zero Data Retention a nivel de organización/proyecto si el caso de uso y cuenta lo permiten.
- No usar background mode para flujos que requieran compatibilidad estricta con Zero Data Retention.

## WhatsApp Web

`whatsapp-web.js` se considera un bridge no oficial de WhatsApp Web y debe estar aislado del núcleo.
- Node.js 24 LTS.
- Chromium/session data en directorio restringido.
- Sin `sendMessage()` habilitado en MVP.
- Los eventos se escriben a una cola interna/SQLite; la IA no controla directamente la sesión.

## Telegram / Instagram

Preferir APIs oficiales cuando el tipo de cuenta y permisos lo permitan. La capa de ingestión debe normalizar eventos a un esquema canónico sin mezclar credenciales de proveedores.

## Canonical event schema

Campos mínimos:
- `event_id`
- `source`
- `conversation_id`
- `sender_ref`
- `received_at`
- `content_type`
- `content_hash`
- `media_ref`
- `sensitivity`
- `analysis_status`
- `send_status`
- `retention_class`

## Deletion / cleanup

Rutina diaria:
1. hash y deduplicación;
2. eliminación de temporales vencidos;
3. conservación de manifests;
4. no borrar originales marcados ARCHIVAL/RESTRICTED sin decisión explícita;
5. generar receipt de limpieza.
