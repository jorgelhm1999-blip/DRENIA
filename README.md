# DRENIA — aplicación de escritorio local

Selecciona un GeoTIFF, calcula y visualiza la red de drenaje, marca sobre ella el punto de vertido y delimita su cuenca. También puedes introducir directamente las coordenadas X/Y del punto en el CRS del MDT. La aplicación busca otras teselas en la carpeta elegida, las incorpora si la cuenca llega a un borde y vuelve a calcular hasta que deja de crecer. No necesita QGIS, navegador, servidor ni Node.js para funcionar.

## Obtener `DRENIA.exe` sin instalar Python en tu ordenador

1. En el repositorio de DRENIA conserva `.github/workflows/windows.yml`; no subas los MDT al repositorio.
2. Abre **Actions → Construir DRENIA para Windows → Run workflow**.
3. Al terminar, descarga el artefacto **DRENIA-Windows**, descomprímelo y ejecuta `DRENIA.exe` dentro de la carpeta descargada. **Conserva toda la carpeta** junto al `.exe`.

El proceso empaqueta Python, las bibliotecas GIS y WhiteboxTools en el equipo Windows de GitHub. El uso posterior del programa es local. La construcción requiere que el servidor de WhiteboxTools esté disponible en ese momento. Si tu organización restringe GitHub Actions, puedes construirlo en un Windows con Python 3.12: descarga el ejecutable oficial `whitebox_tools.exe` a `bin/` y ejecuta `build_windows.bat`.

## Uso

1. Coloca las teselas originales `.tif`/`.tiff` en una carpeta local. Selecciona la carpeta y la tesela donde se encuentra el punto de vertido. La vista intenta cargar automáticamente la ortofoto PNOA por Internet. También puedes escoger una ortofoto GeoTIFF RGB local. La barra «Transparencia de ortofoto» comienza en 0 % (visible) y permite ver gradualmente el MDT; al 100 % se ve únicamente el MDT. El cálculo hidrológico se ejecuta localmente.
2. Elige una carpeta de resultados **distinta de la carpeta de MDT** y pulsa **Calcular y mostrar cauces**. La aplicación dibuja en azul las celdas con al menos el área aportante indicada (por defecto 0,05 km²). Puedes bajar el umbral y pulsar **Actualizar umbral de cauces** si no aparecen cauces. Esta red **preliminar** solo utiliza la tesela inicial: la aportación real puede aumentar cuando se añadan teselas aguas arriba.
   En las pestañas **MDT**, **Dirección D8** y **Acumulación** puedes inspeccionar los productos de este paso. La dirección usa colores para los ocho vecinos receptores y no representa una pendiente ni una elevación. La acumulación se colorea según el número de celdas aportantes en escala logarítmica: colores más claros indican mayor acumulación. Son vistas reducidas para inspección; los rásteres originales conservan la malla de 2 m. Tras delimitar, las vistas pasan a los resultados del mosaico final. La ortofoto y la línea azul de cauces aparecen en la vista MDT.
3. Acerca el visor y haz clic sobre el cauce deseado. También puedes escribir sus coordenadas X/Y en el CRS del MDT y pulsar **Situar punto por coordenadas**. Antes de calcular la cuenca verás en cian la celda de cauce más próxima dentro del radio (por defecto 6 m), el desplazamiento y su aportación preliminar. Si no hay cauce dentro del radio, modifica el punto, el umbral o el radio. Si conoces coordenadas exactas, puedes introducirlas y delimitar sin calcular antes los cauces.
4. Pulsa **Delimitar cuenca**. El programa conserva la celda de vertido confirmada, reutiliza los cálculos previos de la tesela inicial y te avisa si debe incorporar más teselas.
5. Comprueba el estado **COMPLETA** o **PROVISIONAL**, el área y la posición ajustada. El estado provisional indica que la cuenca llega al límite de los datos disponibles o a una tesela incompatible. Añade las teselas que falten y recalcula.
6. Si la cuenca de referencia invade otra hoja, escoge esa hoja en «Comprobar teselas vecinas» y pulsa **Auditar y comparar**. Puedes elegir «Todas las teselas vecinas» si procede; esta opción puede requerir más tiempo y memoria. La auditoría conserva el mismo punto de vertido, repite el análisis incluyendo las teselas indicadas y guarda otra cuenca y un ráster de diferencias. En `diferencias_auditoria.tif`, 1 significa **solo en la cuenca original**, 2 significa **solo en la auditada** y 0 significa **sin diferencia**. `comparacion.json` informa las superficies ganadas y perdidas y el porcentaje de coincidencia espacial. Si aparecen diferencias en el límite de la hoja omitida, la selección automática de teselas influyó en la primera delimitación. Si persisten discrepancias con QGIS, revisa el punto, el tratamiento de depresiones, el modelo de flujo y el MDT empleado.

Los MDT deben tener coordenadas horizontales en metros (por ejemplo ETRS89/UTM), misma proyección, resolución y retícula alineada. Las teselas incompatibles se señalan en `resultado.json` y no se remuestrean silenciosamente. El programa usa la primera banda. En caso de rasters con huecos NoData, estos se comprueban igual que los bordes. Los TIFF de salida previos deben quedar fuera de la carpeta de MDT.

## Reabrir un análisis ya calculado

Pulsa **Abrir análisis guardado…** y selecciona la carpeta que contiene `resultado.json`, `cuenca_mascara.tif` y `pasada_XX/` o `preparacion/`. DRENIA valida los archivos, muestra de nuevo la cuenca, los cauces y las vistas D8 sin volver a ejecutar WhiteboxTools. La carpeta puede moverse completa. Para auditar o recalcular, las teselas originales deben seguir accesibles; si ya no están en la ruta original, elige su carpeta cuando aparezca el diálogo. Si omites el diálogo, puedes consultar el resultado; para asociar las teselas después, vuelve a abrir el análisis guardado. Conserva toda la carpeta de resultados, incluidas las subcarpetas de cada pasada.

## Precipitación y superficies de usos

Tras delimitar o reabrir una cuenca, pulsa **Usos, precipitación y caudales…**. Introduce Cv (admite coma decimal); los YT de T2 a T500 se actualizan según la tabla aportada de *Máximas lluvias diarias en la España peninsular*. Se admiten Cv entre 0,30 y 0,52 y se interpola linealmente entre filas; fuera de ese intervalo se solicita otro dato, sin extrapolar. Selecciona **Usos del Suelo_Corregidos.gpkg** desde tu equipo y pulsa **Calcular superficies**. DRENIA corta los polígonos por `cuenca.gpkg`, presenta las hectáreas por `TC_SIOSE_C` y guarda `superficies_usos.json` con las superficies, la fuente y la diferencia entre la suma clasificada y el área vectorial. Una diferencia distinta de cero puede indicar huecos o solapamientos en la cartografía. La capa original de 131 MB no se incluye en el ejecutable ni en GitHub: elígela desde una carpeta privada.

La tabla de usos incorpora equivalencias revisables con la tabla 2.3 de la 5.2-IC. El **grupo B** se selecciona inicialmente y puede cambiarse a **A, C o D** para todas las superficies. En las filas agrícolas pertinentes se usa la hipótesis **pendiente <3 % y práctica R/N**; las filas sin columna de pendiente o práctica se mantienen tal como aparecen en la norma. Selecciona un uso de la tabla y cambia su fila normativa en el desplegable para corregir una equivalencia; se conserva en `umbrales_52ic.json`. Los cultivos herbáceos cuyo `SIOSE_CODE` es exactamente `CHLsc` o `CHLrr` se separan como secano y regadío; para el secano se presupone la fila de cereales. Los usos SIOSE que engloban categorías distintas de la norma, como el resto de «Cultivo herbáceo» o «Red viaria o ferroviaria», quedan marcados **Revisar** hasta que se asigne una fila. **P₀ⁱ ponderado** solo aparece cuando todos los usos tienen equivalencia. El umbral se pondera por superficie y debe revisarse cuando la cartografía presente huecos o solapamientos.

El desplegable de filas recoge **116 entradas** de la tabla 2.3: todas las filas con usos distintos, conservando solo la variante **pendiente <3 %** y **R/N** cuando esas condiciones distinguen filas del mismo uso. Las claves con sufijo distinguen usos diferentes que la norma agrupa bajo un mismo código, por ejemplo `21100-abandonadas`, `21100-viveros` y `21100-hortalizas`.

Pulsa **Guardar** para conservar Cv, grupo de suelo, fuente y equivalencias. La ubicación se muestra junto al botón; por defecto es la carpeta de resultados indicada en el paso 4, donde ya están `resultado.json` y los TIFF. **Guardar en…** permite elegir otra carpeta para los archivos de análisis (`superficies_usos.json`, `umbrales_52ic.json`, `parametros_caudales.json` y `caudales.json`). DRENIA deja `config_analisis.json` en la carpeta original de la cuenca para recordar la ubicación elegida. Al volver a abrir el análisis se cargan las superficies y equivalencias guardadas sin repetir el corte del GeoPackage.

En **Parámetros y caudales…** introduce precipitación diaria media (mm), βm regional, I₁/Id (inicialmente 10), los FT de cada periodo, y Tc directo o la longitud y pendiente media del cauce para calcularlo. La intensidad, KA, Kt, el coeficiente de escorrentía y los caudales se obtienen por el método racional de la 5.2-IC. Si falta FT para un periodo queda indicado; los demás se calculan. **Guarda los parámetros** aun sin completar el estudio y recupéralos al abrir la ventana de nuevo. La longitud y pendiente del cauce aún se introducen manualmente; la máscara de cuenca por sí sola no proporciona un perfil validado del cauce. No se genera Excel por ahora.

## Método y resultados

El mosaico se escribe **por bloques en disco**. WhiteboxTools aplica `BreachDepressionsLeastCost` con relleno residual, dirección `D8Pointer`, acumulación en número de celdas y `Watershed`. Al pulsar sobre el cauce calculado se escoge la **celda más cercana** que supera el umbral, evitando que el vertido se desplace aguas abajo buscando la máxima acumulación. La celda elegida permanece fija cuando se amplía el mosaico. Sin el cálculo previo de cauces se conserva el ajuste tradicional por máxima acumulación. La búsqueda de brechas se controla con el número de celdas indicado (por defecto 50). La extensión se calcula contando celdas de la máscara final por la superficie de cada píxel, sin simplificar el borde.

La carpeta de resultados contiene:

| Archivo | Contenido |
| --- | --- |
| `cuenca.gpkg` | Polígono de la cuenca en el CRS original, listo para QGIS. |
| `cuenca_mascara.tif` | Máscara ráster georreferenciada (1 = cuenca). |
| `resultado.json` | Área, CRS, teselas utilizadas, posición elegida y ajustada, estado de cobertura y parámetros. |
| `preparacion/` | Mosaico, MDT corregido, dirección D8 y acumulación de la tesela inicial; permite volver a probar otros puntos sin repetirlos. |
| `pasada_01/`, `pasada_02/`… | Mosaico y resultados intermedios de cada ampliación. |

La metodología D8 y la corrección de depresiones son decisiones hidráulicas que pueden alterar divisorias, especialmente ante puentes, terraplenes, rellenos y vaguadas modificadas. El ajuste a máxima acumulación puede mover el vertido a otro ramal si el radio es excesivo. Comprueba el trazado sobre ortofoto y cartografía de cauces antes de emplearlo en un documento técnico. El estado **COMPLETA** confirma que la cuenca no toca huecos ni límites del conjunto de teselas disponible; no garantiza por sí mismo la calidad del MDT.

La capa «Drainage Basins» de SAGA/QGIS divide la superficie en cuencas de drenaje y permite una comparación visual de divisorias. DRENIA **no la usa para recortar ni forzar la cuenca**: calcula el área aportante específica al punto de vertido con `Watershed` de WhiteboxTools. Un área total parecida a la de QGIS no demuestra por sí sola que las dos cuencas ocupen las mismas celdas. La selección automática incorpora nuevas hojas al detectar que su propia cuenca llega a un borde; para comprobar una hoja vecina que no detectó se usa la auditoría del paso 6.

Para probar los cálculos antes de usar datos reales: `python smoke_test.py RUTA_A_whitebox_tools`. La prueba crea dos teselas sintéticas de 2 m, dibuja y reutiliza la red previa, fuerza una ampliación y comprueba el área y los formatos exportados.

## Si falla un cálculo

El campo «Motor hidrológico» se deja vacío con la versión de Windows descargada: el programa encuentra automáticamente el ejecutable incluido. Escoge una carpeta de resultados local y con suficiente espacio libre, separada de las teselas de entrada. Cada pasada guarda un `registro_motor.txt` con la salida íntegra y el código de error. Si aparece un error al «Saving data...», conserva el registro de `pasada_01` y la dimensión en píxeles de la tesela; esos datos permiten distinguir falta de espacio, un fallo de WhiteboxTools o un límite del archivo. No consideres válido un resultado parcial.
