# PREDWEEM LOLIUM — Plataforma multisitio

Repositorio integrador para la predicción operativa de emergencia de *Lolium* en nueve localidades.

## Arquitectura de repositorios

```text
PREDWEEM/MULTISITIO
└── aplicación regional, catálogo de sitios y actualización meteorológica integrada

PREDWEEM/LOLIUM_ZAVALLA2026
└── aplicación y meteorología independiente de Zavalla
```

## Localidades y política operativa

| Localidad | Modelo |
|---|---|
| Azul | Sin lag |
| Balcarce | Sin lag |
| Bordenave | Sin lag |
| Lartigau | Sin lag |
| Olavarría | Sin lag |
| San Pedro | Sin lag |
| Tres Arroyos | Sin lag |
| Pergamino | Lag fijo de 15 días |
| Zavalla | Lag fijo de 15 días |

El catálogo geográfico y la política de modelo se definen en `sitios_lolium.py`. Las calibraciones de las nueve localidades se encuentran exclusivamente en `config_multisitio.py`.

## Archivos operativos

```text
app.py                         entrada de Streamlit
app_multisitio_principal.py    interfaz regional
app_multisitio.py              utilidades de simulación e interfaz
app_fuente_hibrida.py          trazabilidad meteorológica de Zavalla
app_detalle_1pct.py            detalle de baja emergencia
app_umbral_operativo.py        criterio EMERREL >= 0,0001
app_zoom_operativo.py          zoom, paneles y mapa

sitios_lolium.py               catálogo de localidades
config_multisitio.py           calibraciones y parámetros operativos
predweem_core.py               motor ANN y ecofisiológico
visualizacion_operativa.py     gráficos principales
visualizacion_pulsos.py        agrupación de pulsos
mapa_sitios.py                 mapa regional

update_meteo.py                punto de entrada meteorológico seguro
update_meteo_core.py           motor de actualización
update_meteo_runtime.py        alias compatible del actualizador

data/meteo_sitios/*.csv       series meteorológicas por localidad
data/estado_actualizacion_meteo.json

IW.npy, bias_IW.npy, LW.npy, bias_out.npy
                               activos de la red neuronal
```

Los módulos encadenados desde `app.py` se conservan porque forman parte de la interfaz multisitio activa. No son aplicaciones independientes.

## Meteorología

Para Azul, Balcarce, Bordenave, Lartigau, Olavarría, Pergamino, San Pedro y Tres Arroyos se mantienen copias exactas de los archivos meteorológicos de sus repositorios geográficos.

Para Zavalla se aplica prioridad por variable:

```text
SMN Rosario Aero 87480
→ NOAA NCEI, cuando esté disponible
→ Open-Meteo ECMWF IFS Archive para faltantes
→ Open-Meteo ECMWF IFS Forecast desde el día actual
```

Las columnas `Fuente_TMAX`, `Fuente_TMIN` y `Fuente_Prec` registran la procedencia efectiva.

## Componentes eliminados

La plataforma no selecciona modelos mediante conteos de campo. Por ese motivo no deben existir en `main`:

```text
selector_adaptativo.py
data/inspecciones_campo.csv
data/selector_estado.json
config_zavalla.py
```

La ausencia de estos archivos y la presencia de las nueve localidades se controlan en `tests/test_multisitio_registry.py`.

## Ejecución

```bash
python -m pip install -r requirements.txt
python update_meteo.py
streamlit run app.py
```

## Validación

```bash
python -m py_compile \
  app.py app_multisitio.py app_multisitio_principal.py \
  config_multisitio.py sitios_lolium.py predweem_core.py \
  visualizacion_operativa.py visualizacion_pulsos.py \
  update_meteo.py update_meteo_core.py

python -m pytest tests -q
```

La rama `pre-depuracion-multisitio-20260802` conserva el estado inmediatamente anterior a esta limpieza.

**PREDWEEM by Guillermo R. Chantre**
