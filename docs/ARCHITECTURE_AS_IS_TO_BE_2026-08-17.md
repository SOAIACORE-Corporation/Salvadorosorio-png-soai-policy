# SOAiaCore · AS-IS → TO-BE Hardening

Fecha: 2026-08-17
Estado: PROPOSED / NO-PRD-MERGE

## 1. Principios operativos

Cadena obligatoria: `CONTEXT → SYNC → PRECHECK → CHANGE/BUILD → VALIDATE → RECEIPT`.

Reglas:
- No declarar un componente como desplegado sin evidencia de ejecución.
- No mezclar salida de consola con comandos ejecutables.
- Ningún secreto en Git, logs, query strings o frontend.
- Ningún servicio de aplicación corre como root.
- Todo cambio debe ser idempotente, auditable y reversible.
- Toda integración de mensajería inicia en `OBSERVE_ONLY=true`.
- Análisis sensible y publicación/respuesta requieren aprobación humana explícita.

## 2. AS-IS verificable

Fuentes canónicas recuperadas en Drive:
- SOA_CONTEXT_CAPSULE.
- SOA_MASTER_INDEX.
- SOA_CHANGELOG.
- SOA_ACTIVE_WORK.

Repositorio conectado:
- `SOAIACORE-Corporation/Salvadorosorio-png-soai-policy`.
- Rama por defecto: `main`.
- Estado raíz observado: probes de salud/PRD y README.

Infraestructura histórica conocida por evidencia aportada en conversación:
- Ubuntu 24.04 LTS.
- systemd.
- Python 3.12 del sistema.
- UFW.
- IP pública histórica `64.227.28.84`.
- intentos previos de Flask en `:5000`.

Problemas AS-IS detectados:
1. Scripts efímeros que existían sólo en chat.
2. Uso fallido de `pip3 install` global bajo PEP 668.
3. Configuraciones Nginx/Certbot intentadas antes de instalar/verificar servicios y DNS.
4. Archivos referenciados con rutas inexistentes (`/mnt/data`, ZIPs no transferidos).
5. Mezcla de transcript/logs con comandos, provocando `command not found` masivo.
6. Estado reportado como “ejecutado” sin telemetría o receipt verificable.

## 3. TO-BE mínimo viable y moderno

### Runtime
- Ubuntu 24.04 LTS.
- Python 3.12 en `venv` dedicado para API/OCR/orquestación.
- Node.js 24 LTS para bridges de mensajería que lo requieran.
- Nginx como reverse proxy.
- systemd para lifecycle, restart y sandboxing.
- SQLite para MVP; migración a PostgreSQL sólo cuando haya carga/concurrencia que lo justifique.

### OpenAI
- OpenAI Responses API desde backend.
- `OPENAI_API_KEY` sólo en archivo de entorno protegido o secret manager.
- `store=false` por defecto para contenido sensible cuando no se necesite retención de estado por API.
- request IDs y métricas sin contenido sensible en logs.

### Capas
1. `ingest/`: WhatsApp/Telegram/Instagram y cargas manuales.
2. `media/`: hash, deduplicación, metadatos y lifecycle.
3. `ocr/`: Tesseract local + análisis multimodal opcional.
4. `classification/`: keywords, FYG, etiquetas, riesgo, sensibilidad.
5. `approval/`: gate humano obligatorio.
6. `api/`: FastAPI local-only en `127.0.0.1:8940`.
7. `web/`: panel editorial y radar.
8. `backup/`: Drive/local cifrado, separado del runtime.
9. `audit/`: receipts, hashes, versiones y fallos.

## 4. Política de mensajería

Estados por evento:
- `INGESTED`
- `PENDING_ANALYSIS_APPROVAL`
- `ANALYZED`
- `DRAFT_SUGGESTED`
- `PENDING_SEND_APPROVAL`
- `SENT` (sólo por acción humana)
- `DISCARDED`

Nunca existe transición automática `DRAFT_SUGGESTED → SENT`.

## 5. Seguridad

- Usuario de servicio dedicado: `soaia`.
- Directorio recomendado: `/opt/soaia`.
- Datos mutables: `/var/lib/soaia`.
- Logs: journald + `/var/log/soaia` sólo si se requiere exportación.
- `umask 027`.
- Firewall: 22, 80, 443; puertos internos no expuestos.
- TLS sólo después de confirmar resolución DNS correcta.
- Backups cifrados antes de salir del host cuando contengan material sensible.
- Tokens OAuth/API fuera del repositorio.

## 6. Observabilidad

Health endpoints:
- `/health/live`
- `/health/ready`

Receipt mínimo por despliegue:
- timestamp UTC
- git commit
- host
- versión OS
- servicio y estado
- checks ejecutados
- resultado PASS/FAIL
- checksum de archivos críticos

## 7. Change Lock

Este documento no autoriza modificar producción. La rama de hardening debe validarse y abrir PR. Merge a `main` sólo cuando PRECHECK y rollback estén documentados.
