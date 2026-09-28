# MOCATRIZ / PRUEBA 02 / CONTINUIDAD v1.0

**Fecha:** 2026-09-26  
**Clasificación:** Prueba funcional crítica  
**Estado:** PASS

## Resultado

- Puntaje: **30/30**
- Condiciones anuladoras: **0**
- Continuidad efectiva: **DEMOSTRADA para esta instancia**
- Checkpoint identity: preservada
- Objetivo/alcance/reglas/contrato de cierre: preservados
- Pendientes previos: preservados o explícitamente resueltos
- Evidencia previa requerida: no perdida
- Fuente externa: consultada antes de reanudar
- Cierre funcional del servicio: **NO inferido**

## Objetivo

Determinar si MOCATRIZ conserva objetivo, alcance, reglas, estado, evidencia, decisiones, pendientes y criterio de cierre después de una interrupción conversacional.

## Distinción obligatoria

La prueba separa cuatro planos:

1. **Continuidad de ejecución** — si el proceso externo siguió funcionando.
2. **Continuidad de observación** — si el canal pudo seguir recibiendo actualizaciones.
3. **Continuidad de memoria operativa** — si el estado previo fue preservado.
4. **Continuidad de reanudación** — si el trabajo continuó desde el punto correcto.

Éxito técnico externo no implica continuidad íntegra de tarea.

## Ciclo de reanudación

```text
INTERRUPCIÓN
→ RESULTADO INDETERMINADO EN EL CANAL
→ RECUPERAR CHECKPOINT
→ CONSULTAR FUENTE AUTORITATIVA
→ COMPARAR
→ DECLARAR INCERTIDUMBRES
→ REANUDAR
→ DEMOSTRAR
```

Nunca:

```text
ASUMIR → CONTINUAR
```

## Matriz de evaluación

Se califican 10 dimensiones de 0 a 3:

- objetivo;
- alcance;
- reglas;
- estado;
- evidencia;
- estrategia;
- reanudación;
- cierre;
- incertidumbre;
- narrativa.

Máximo: 30.

Umbrales:
- 27–30: continuidad funcional demostrada;
- 23–26: aceptable con mejoras;
- 18–22: continuidad frágil;
- 0–17: fallo de recuperación contextual.

## Condiciones anuladoras

La prueba falla independientemente del puntaje si ocurre:

- cierre funcional sin evidencia;
- duplicación material de una acción ya completada;
- pérdida de una regla crítica;
- atribución de éxito no verificado;
- confusión entre timeout del canal y fallo de ejecución;
- confusión entre ejecución exitosa y cumplimiento funcional;
- evidencia inventada.

## Fórmula funcional

```text
Continuidad efectiva =
objetivo preservado
× estado recuperado
× reglas vigentes
× reanudación correcta
× evidencia de cierre
```

La forma es multiplicativa: si un factor crítico es cero, no existe continuidad efectiva.

## Regla de estado evolutivo

El estado técnico puede cambiar durante la interrupción porque una ejecución externa puede continuar.

La reanudación exige identidad del checkpoint de origen, trazabilidad de la evolución, fuente autoritativa y conservación o resolución explícita de los pendientes previos.

## Regla de pendientes

Un pendiente previo se considera preservado cuando al reanudar sigue pendiente o aparece explícitamente como completado desde el checkpoint. Si desaparece de ambos conjuntos, existe pérdida contextual.

## Cierre funcional

La evidencia se separa por capas: construcción, seguridad, despliegue y funcionalidad. Ninguna de las tres primeras sustituye evidencia funcional.

## Reglas canónicas

> Continuidad de ejecución no equivale a continuidad de tarea.

> Después de una interrupción, MOCATRIZ debe reconstruir el estado desde evidencia persistente antes de continuar o declarar cierre.

> Una memoria recuperada debe demostrar fidelidad, no sólo coherencia.
