# Bitácora del asistente de código — PE4 (servidor MCP y agente)

El código de la PE4 lo construyó Claude (en la app, con acceso al repo) a partir de los pedidos de Federico. Esta bitácora registra los pedidos que dieron forma al servidor MCP y los errores del asistente que se detectaron y corrigieron. Fecha: 2026-11-16.

## Prompts

### Prompt 1 — el pedido de la entrega (Federico)

> «En la carpeta de FDE está la clase 4, esto es el requisito de entrega» (con la consigna de la PE4 adjunta: grafo en LangGraph, servidor MCP propio con al menos 2 herramientas tipadas, una de lectura y una de escritura, sistema del cliente simulado en SQLite, aprobación humana con interrupt, 5 conversaciones con traza).

Resultado: el diseño del sistema simulado (`src/sistema.py`) y del servidor (`src/mcp_servidor.py`) con `consultar_ccam`, `listar_ccam` y `registrar_evaluacion`.

### Prompt 2 — la regla de aprobación (Federico)

> «Lo aprueba QA formalmente, no debe ser el mismo que lo pidió.»

Resultado: segregación de funciones en dos capas. El agente valida la aprobación en `pedir_aprobacion` (rol `jefe_qa` y distinto de quien pidió) y el servidor MCP la vuelve a validar en `registrar_evaluacion`, porque el sistema no puede confiar en que el cliente haga bien su parte.

### Prompt 3 — el pedido técnico (armado por el asistente a partir de 1 y 2, y aplicado)

> «Servidor MCP por stdio con tres herramientas. Parámetros tipados con `Annotated` y `Field` (patrón del número de CCAM, Enum de impacto y de estado, citas con formato `CÓDIGO §sección`). Descripciones que digan si la herramienta es de lectura o de escritura y cuándo usarla. Errores de negocio como `ToolError` con mensaje en español. El agente no elige los datos que se escriben: solo el `id_ccam`; el borrador sale de su propia evaluación en esa conversación.»

Resultado: las descripciones que lee el modelo salen del servidor (`list_tools`) y se inyectan en `prompts/agente.md`: una sola fuente de verdad.

## Errores del asistente detectados y corregidos

| # | Error | Cómo se detectó | Corrección |
| --- | --- | --- | --- |
| E-1 | Escribió el servidor con `from mcp.server.fastmcp import FastMCP`, la API que conocía. En la versión instalada (`mcp` 2.3) se llama `MCPServer`. | El primer arranque falló con `No module named 'mcp.server.fastmcp'`. | `from mcp.server.mcpserver import MCPServer`. Se fijó la versión en `requirements.txt` (`mcp>=2.3,<3`). Lección: probar contra la librería instalada, no contra lo que «se sabe». |
| E-2 | Las herramientas avisaban los errores con `ValueError`. El servidor los trataba como una falla inesperada: el cliente recibía solo «Error executing tool» y el traceback quedaba en la consola. | Al llamar `consultar_ccam("CCAM-2026-999")` desde el script cliente. | `ToolError`: el cliente recibe «No existe el CCAM-2026-999…». Coincide con la regla del proyecto: nunca un traceback al usuario. |
| E-3 | La prueba de segregación del script cliente usaba `u_analista_qa` como solicitante y aprobador. Fallaba, pero por otro motivo (no es QA formal), así que no probaba la segregación. | Al leer el mensaje de error: decía «no es QA formal», no «quien pide no puede aprobar». | La prueba usa `u_jefe_qa` en los dos lados, y en `tests/test_agente.py` hay un caso por cada motivo de rechazo. |
| E-4 | La plantilla de corrección decía «volvé a responder con la herramienta registrar_propuesta». En el agente la herramienta se llama `decidir_paso`: un reintento le habría pedido al modelo usar una herramienta equivocada. | Al revisar el reintento compartido entre el motor y el agente. | `$herramienta` en `prompts/correccion.md`; el motor completa el nombre real. Cambió la huella de los prompts (queda registrado en cada ejecución). |

Para el PDF se toma E-1: es el error típico de un asistente de código (usar una API de memoria) y se detectó corriendo, no leyendo.
