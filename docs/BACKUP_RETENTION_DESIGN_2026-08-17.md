# SOAiaCore · Backup & Retention Design

Fecha: 2026-08-17
Estado: DESIGNED / NOT DEPLOYED

## Objetivo
Respaldar configuración, manifests, receipts y material seleccionado sin convertir Drive en un segundo volcado indiscriminado de información sensible.

## Política por clase
- EPHEMERAL: no backup; TTL local corto.
- CONTEXTUAL: backup sólo de metadata/manifests cuando sea suficiente.
- ARCHIVAL: backup permitido con hash y manifest.
- RESTRICTED: backup externo sólo cifrado cliente-side y con aprobación explícita.

## Capas
1. Runtime local: `/var/lib/soaia`.
2. Staging de backup cifrado: `/var/lib/soaia/backup-staging`.
3. Destino remoto: carpeta dedicada en Drive.
4. Manifest: SHA-256, tamaño, fecha, clase de retención, versión de esquema.

## Cifrado
Usar un formato de archivo cifrado autenticado gestionado fuera de Drive. Nunca subir claves junto con los respaldos. La clave de cifrado no debe residir en Git ni en el panel web.

## Frecuencia propuesta
- Configuración/receipts: diario.
- Manifests: diario.
- ARCHIVAL seleccionado: diario incremental.
- RESTRICTED: sólo tras aprobación humana y nunca por una regla que copie todo el árbol.

## Rotación
- Receipts: 180 días local + copia remota seleccionada.
- Logs operativos sin payload: 30 días local.
- Temporales OCR/media: TTL configurable; limpieza diaria.
- Backups cifrados: esquema 7 diarios / 4 semanales / 6 mensuales como máximo inicial, revisable por consumo.

## Recuperación
Un backup no se considera válido hasta realizar restore test periódico en un directorio aislado y verificar hashes.

## Gate
No habilitar sync remoto hasta:
1. PRECHECK/receipt de VM;
2. credenciales de Drive gestionadas fuera de Git;
3. cifrado cliente-side probado;
4. restore test PASS;
5. política de retención confirmada.
