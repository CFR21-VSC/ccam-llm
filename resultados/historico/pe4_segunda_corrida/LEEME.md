# Segunda corrida real de la PE4 (no es la de la entrega)

Corrida del 2026-11-17 con Claude Haiku 5.5, commit `679cc6c`. C1 a C4 salieron como se esperaba: C3 se aprobó y se retomó en otro proceso, y C4 se rechazó sin escribir. Se guarda por un hallazgo:

- **H-27** C5 no llegó al corte del sistema. El prompt le decía al modelo «Paso 3 de 3» y el modelo eligió responder por su cuenta en el último paso. Es un comportamiento razonable, pero deja sin probar la barrera de código. Decisión D-33: el modelo no conoce el número máximo; el límite es un control del sistema, no una instrucción que el modelo puede seguir o no. Corrección en `prompts/agente.md` y en el nodo decidir.
