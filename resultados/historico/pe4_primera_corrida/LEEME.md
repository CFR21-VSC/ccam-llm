# Primera corrida real de la PE4 (no es la de la entrega)

Corrida del 2026-11-17 00:10 con Claude Haiku 5.5, commit `3ee7666`. Se guarda como evidencia de dos hallazgos:

- **H-25** C3 y C4: el modelo evaluó el CCAM pero no eligió `registrar_evaluacion`. Leyó «requiere aprobación humana previa» como que la aprobación tenía que existir antes de pedir la escritura, y razonó que un analista no puede aprobar. La consigna exige que elegir la escritura sea lo que dispara la pausa. Corrección: la regla 2 de `prompts/agente.md` y la descripción de la acción dicen que elegirla es la forma de pedir la aprobación.
- **H-26** C3: la respuesta final superó dos veces el máximo de 1.500 caracteres y la conversación cerró con error estructurado (sin traceback). Corrección: tope de 1.000 caracteres en el prompt y máximo de 2.000 en el contrato de `Decision`.

En esta corrida no se escribió nada en el sistema (0 escrituras): el control funcionó aunque el agente no pidió la escritura.
