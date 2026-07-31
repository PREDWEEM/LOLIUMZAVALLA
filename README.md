# PREDWEEM LOLIUM — Selector geográfico sin lag / con lag

Implementación adaptativa de PREDWEEM con selección del **sitio geográfico específico** y decisión supervisada entre dos hipótesis temporales de emergencia de *Lolium*:

- **modelo sin lag**: alerta anticipada;
- **modelo con lag fijo**: señal filtrada desplazada el número de días configurado;
- **ninguno confirmado**: diagnóstico posterior cuando tampoco se confirma la ventana con lag.

El sistema no estima lags locales intermedios.

## Sitios disponibles

El catálogo `sitios_lolium.py` reúne todas las implementaciones geográficas LOLIUM accesibles de PREDWEEM:

| Sitio | Provincia | Repositorio de referencia |
|---|---|---|
| Azul | Buenos Aires | `PREDWEEM/LOLIUM_AZUL2026` |
| Balcarce | Buenos Aires | `PREDWEEM/LOLIUM_BAL2026` |
| Bordenave | Buenos Aires | `PREDWEEM/LOLIUM_BOR2026` |
| Lartigau | Buenos Aires | `PREDWEEM/LOLIUM_LARTIGAU-2026` |
| Olavarría | Buenos Aires | `PREDWEEM/LOLIUM_OLAVA2026` |
| Pergamino | Buenos Aires | `PREDWEEM/LOLIUM-PERGA2026` |
| San Pedro | Buenos Aires | `PREDWEEM/lolium_sanpedro2026` |
| Tres Arroyos | Buenos Aires | `PREDWEEM/loliumTA_2026` |
| Zavalla | Santa Fe | `PREDWEEM/LOLIUMZAVALLA` |

La selección geográfica cambia:

- nombre, provincia y coordenadas del sitio;
- latitud utilizada en ET0 Hargreaves;
- archivo meteorológico operativo;
- historial de inspecciones;
- estado del selector;
- nombres y metadatos de las exportaciones.

El motor adaptativo y sus umbrales científicos continúan siendo comunes. La calibración local definitiva debe sostenerse con validación de campo para cada sitio.

## Meteorología multisitio

`update_meteo.py` descarga y valida una serie independiente para cada localidad usando ECMWF IFS mediante Open-Meteo:

```text
data/meteo_sitios/azul.csv
data/meteo_sitios/balcarce.csv
data/meteo_sitios/bordenave.csv
data/meteo_sitios/lartigau.csv
data/meteo_sitios/olavarria.csv
data/meteo_sitios/pergamino.csv
data/meteo_sitios/san-pedro.csv
data/meteo_sitios/tres-arroyos.csv
data/meteo_sitios/zavalla.csv
```

`meteo_daily.csv` se conserva como copia compatible de Zavalla.

El workflow **Actualizar meteorología multisitio LOLIUM** se ejecuta dos veces por día y también admite ejecución manual. Primero descarga y valida los nueve sitios; solo después escribe los archivos, evitando actualizaciones parciales.

## Aislamiento de datos de campo

Cada sitio mantiene archivos independientes:

```text
data/inspecciones/<sitio>.csv
data/selector/<sitio>.json
```

Cambiar de localidad no mezcla conteos, decisiones ni estados operativos.

## Parámetros térmicos de las hipótesis

- modelo sin lag: termoinhibición cuando `Tmedia_5d >= 24 °C`;
- modelo con lag: termoinhibición cuando `Tmedia_5d >= 20 °C`;
- lag fijo predeterminado: `+15 días`;
- ventana fenológica: `600–800 °Cd` desde el pico del modelo visible.

## Selección mediante conteos

1. Sin conteos: ambos modelos permanecen visibles.
2. Primer conteo negativo: se solicita una segunda verificación.
3. Dos conteos iniciales negativos: se selecciona automáticamente el modelo con lag fijo y se oculta el modelo sin lag.
4. Una presencia positiva dentro de los dos conteos iniciales confirma el modelo sin lag.
5. Una observación posterior en la ventana desplazada confirma el modelo con lag.
6. Para rechazar ambos modelos se requiere una verificación negativa adicional en la ventana con lag.

## Visualización

Los flujos diarios se muestran como línea fina para auditoría. Las activaciones próximas se agrupan en campanas gaussianas suaves con área coloreada. Una vez seleccionado un modelo, solo permanecen sus pulsos y su ventana fenológica.

## Ejecución

```bash
python -m pip install -r requirements.txt
python update_meteo.py
streamlit run app.py
```

## Validación

```bash
python -m pytest -q
python -m py_compile app.py predweem_core.py selector_adaptativo.py \
  visualizacion_pulsos.py update_meteo.py config_zavalla.py sitios_lolium.py
```

## Persistencia

Streamlit Community Cloud puede utilizar un sistema de archivos efímero. Las inspecciones pueden descargarse y restaurarse, pero para operación productiva se recomienda almacenamiento persistente externo.

## Autoría

**PREDWEEM by Guillermo R. Chantre**

PREDWEEM es una herramienta de soporte y no reemplaza el monitoreo a campo ni el criterio profesional agronómico.
