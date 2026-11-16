# Corrida entregada en la PE2 (30/10/2026)

Estos son los archivos que respaldaron el PDF de la Pre-Entrega 2. Se conservan sin cambios como registro.

Tienen un problema que señaló la devolución del docente: la evidencia de la ejecución exitosa (`evidencia_exito.txt`) y la fila 1 de la tabla (`medicion_20261030_1626.*`) salieron de **dos llamadas distintas** al modelo, por eso sus tokens y costos difieren (2497/1160 contra 2497/1162). Desde la corrección, toda medición se hace con `python -m scripts.corrida`, que genera una sola carpeta con manifiesto y hashes.
