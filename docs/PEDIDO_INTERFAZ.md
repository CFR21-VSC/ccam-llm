# Pedido: interfaz visual local del motor (Streamlit)

Pedido para Claude Code. Leer antes `CLAUDE.md`, `docs/ESTADO.md` y `docs/COMO_FUNCIONA.md`.

## Cuándo hacerlo

**Después** de cerrar la PE2: repo subido, corrida real hecha y tag `pe2` puesto. La interfaz no es parte de la consigna de la PE2, así que no tiene que arriesgar esa entrega. Va en un commit aparte, sobre la rama principal.

## Para qué

Federico no programa. Necesita **ver** cómo trabaja el motor para entenderlo, mostrarlo en la demo de 5 minutos de la PE10 y defenderlo en vivo. Además es la base de la pantalla de QA de la PE4, donde se va a aprobar o rechazar cada propuesta.

## Qué construir

Un archivo nuevo `app.py` en la raíz, con [Streamlit](https://streamlit.io), que se levanta con:

```bash
streamlit run app.py
```

y se abre en el navegador local. Todo en español rioplatense.

### Pantalla única, de arriba hacia abajo

1. **Encabezado:** "Motor de evaluación de impacto de CCAM". Debajo, en chico: modelo activo, proveedor y versión del prompt (`version_prompt()`).

2. **Barra lateral, modo de ejecución:**
   - Selector: `Claude (real)` o `Simulado`. Si no hay `ANTHROPIC_API_KEY` en el entorno, `Claude (real)` aparece deshabilitado con el aviso "Cargá la clave en .env para usar el modelo real".
   - Si es `Simulado`, segundo selector con los escenarios: `valido`, `invalido_luego_valido`, `invalido`, `sin_conexion`, `limite_uso`, cada uno con una frase que explique qué muestra.
   - Botones "Cargar caso de prueba" con los 5 archivos de `consultas/` y los 2 de `consultas/extra/`.

3. **Formulario del CCAM:** los campos de `Entrada`. `tipo_cambio` y `area_solicitante` como listas desplegables generadas desde los Enums de `src/contrato.py`, nunca escritas a mano. `descripcion` como área de texto con contador de caracteres y el mínimo de 30 visible. Botón "Evaluar".

4. **Recorrido en vivo:** los pasos del motor como una lista que se va completando mientras corre:
   1. Control de la entrada
   2. Armado de prompts
   3. Llamada al modelo (intento N)
   4. Control de la salida
   5. Reintento con corrección (solo si ocurre)
   6. Medición
   7. Registro en el log

   Cada paso muestra su estado: en curso, OK (verde), falló (rojo). Si falla el control de la salida, debajo del paso se listan los campos que fallaron con su ruta (`fundamento -> 0 -> codigo`) y el problema.

5. **Resultado:**
   - Si valida: una **ficha de propuesta** con el impacto GxP como etiqueta de color (sin impacto, menor, mayor, crítico), si requiere revalidación, la justificación, los SOPs citados con su título del catálogo y sección, las tareas agrupadas por área y la confianza como barra. Arriba de la ficha, bien visible, el sello **BORRADOR · PENDIENTE DE QA**.
   - Si no valida: el `ErrorEstructurado` legible, con tipo de error, campos, intentos y la acción recomendada.
   - Un desplegable "Ver JSON completo" con el `Resultado` tal cual.

6. **Métricas:** cuatro valores en fila: intentos, tokens (entrada / salida), costo en USD y latencia en ms. Debajo, la comparación con la meta de la HU-01: menos de 30 s, deseable 20 s.

7. **Audit trail:** una tabla con las últimas 20 líneas de `logs/ejecuciones.jsonl`, la más nueva arriba, con un filtro por `trace_id` o `id_ccam`. La fila de la ejecución recién hecha aparece resaltada.

## El único cambio permitido en el motor

Para que el recorrido sea en vivo, `evaluar()` necesita avisar en qué paso está. Agregar **un parámetro opcional**:

```python
def evaluar(datos: dict, proveedor=None, al_paso=None) -> Resultado:
```

- `al_paso` es una función opcional que el motor llama en cada paso con un dict simple: `{"paso": "...", "estado": "en_curso" | "ok" | "fallo", "intento": n, "detalle": ...}`.
- Si `al_paso` es `None`, el motor se comporta exactamente igual que hoy.
- Un error dentro de `al_paso` nunca debe romper la evaluación: se atrapa y se ignora.
- Sumar una prueba en `tests/` que verifique la secuencia de pasos para `valido` y para `invalido_luego_valido`.

No tocar nada más de `src/motor.py`, `src/contrato.py`, `src/proveedores.py` ni `prompts/`.

## Reglas

- La interfaz **solo llama** al motor. No duplica validaciones ni reglas de negocio: todo sale de `src/`.
- No muestra ni pide la clave. La lee del entorno como el resto del sistema.
- No escribe en el log por su cuenta: el log lo escribe el motor.
- Agregar `streamlit` a `requirements.txt` con versión acotada.
- Las 16 pruebas actuales siguen en verde.

## Cómo probarlo (criterios de aceptación)

- [ ] `streamlit run app.py` abre la pantalla sin errores, con y sin clave en `.env`.
- [ ] Con `Simulado · valido` y el caso 01, se ve la ficha con el sello de borrador y las métricas.
- [ ] Con `Simulado · invalido_luego_valido`, se ve el control de salida en rojo con el campo `fundamento -> 0 -> codigo`, el reintento y después la ficha válida, con 2 intentos.
- [ ] Con `Simulado · invalido`, se ve el error estructurado con la acción "Derivar a QA para evaluación manual".
- [ ] Con `Simulado · sin_conexion`, se ve el error `api_sin_conexion`.
- [ ] Con `consultas/extra/entrada_invalida.json`, el recorrido se corta en el paso 1 y no se llama al modelo.
- [ ] Con Claude real y el caso 01, se ve la propuesta real, con tokens y costo distintos de cero.
- [ ] Cada evaluación aparece arriba en el audit trail, resaltada.
- [ ] `python -m pytest -q` en verde, incluida la prueba nueva de `al_paso`.

## Al terminar

- `README.md`: sección "Interfaz visual" con el comando y una captura.
- `docs/COMO_FUNCIONA.md`: un párrafo sobre la interfaz y el parámetro `al_paso`.
- `docs/DECISIONES.md`: fila D-13, "Interfaz local con Streamlit antes de la PE4", con su porqué (demo, defensa y base de la pantalla de aprobación de QA) y la alternativa descartada (interfaz web propia con FastAPI y HTML, que llega con la PE8).
- `docs/ESTADO.md`: actualizar la tabla y la bitácora.
- Commit: `Interfaz visual local del motor (Streamlit) y aviso de pasos en evaluar()`.
