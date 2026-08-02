# PREDWEEM LOLIUM — Modelo operativo automático por localidad

Aplicación multisitio para simular la emergencia de *Lolium* con una política de modelo definida previamente para cada localidad.

## Selección automática del modelo

La aplicación no solicita recuentos a campo ni utiliza inspecciones para elegir entre modelos.

| Localidad | Modelo operativo |
|---|---|
| Azul | Sin lag |
| Balcarce | Sin lag |
| Bordenave | Sin lag |
| Lartigau | Sin lag |
| Olavarría | Sin lag |
| San Pedro | Sin lag |
| Tres Arroyos | Sin lag |
| Pergamino | Con lag fijo de 15 días |
| Zavalla | Con lag fijo de 15 días |

La regla está definida en `sitios_lolium.py` mediante los campos:

```python
modelo_operativo
lag_operativo_dias
```

La interfaz muestra, grafica y exporta únicamente el modelo operativo correspondiente al sitio seleccionado.

## Ajuste visible

La única variable de ajuste disponible en la interfaz es:

- **Cobertura de rastrojo (%)**.

Wmax, exponente Kr, termoinhibición, latencia, umbrales de lluvia, decaimiento y lag operativo permanecen fijados por la calibración específica de cada localidad. Estos parámetros se utilizan internamente, pero no se muestran como controles de usuario.

## Sin recuentos de campo

Se eliminaron del flujo operativo:

- formulario de inspección;
- carga y restauración de conteos;
- historial de plantas por metro cuadrado;
- puntos de campo sobre la gráfica;
- selección adaptativa mediante observaciones;
- estado pendiente, provisional o confirmado basado en conteos;
- exportación de inspecciones y estado del selector.

Los archivos históricos de inspecciones pueden permanecer en el repositorio por compatibilidad, pero la aplicación no los lee ni los modifica.

## Meteorología multisitio

Los sitios distintos de Zavalla utilizan copias exactas de `meteo_daily.csv` provenientes de sus repositorios geográficos públicos:

```text
data/meteo_sitios/azul.csv
data/meteo_sitios/balcarce.csv
data/meteo_sitios/bordenave.csv
data/meteo_sitios/lartigau.csv
data/meteo_sitios/olavarria.csv
data/meteo_sitios/pergamino.csv
data/meteo_sitios/san-pedro.csv
data/meteo_sitios/tres-arroyos.csv
```

Para **Zavalla**, la prioridad se aplica independientemente a `TMAX`, `TMIN` y `Prec`:

```text
SMN Rosario Aero 87480
→ NOAA NCEI como respaldo observado, cuando esté disponible
→ Open-Meteo ECMWF IFS Archive para completar faltantes
→ Open-Meteo ECMWF IFS Forecast desde el día actual
```

Las columnas `Fuente_TMAX`, `Fuente_TMIN` y `Fuente_Prec` registran la procedencia efectiva de cada variable. Los códigos negativos de precipitación observada se consideran inválidos y son reemplazados por la siguiente fuente disponible.

El punto de entrada único es:

```bash
python update_meteo.py
```

`update_meteo_core.py` conserva el motor de actualización y `update_meteo.py` instala los controles de calidad antes de ejecutarlo. `update_meteo_runtime.py` permanece únicamente como alias compatible.

## Reloj de grados-día fenológico

El reloj se inicia en el primer pico del modelo operativo y acumula `GD_Tb2` hasta la fecha meteorológica vigente.

Los hitos son:

- **600 °Cd:** inicio de la ventana de máxima susceptibilidad;
- **800 °Cd:** límite operativo de la ventana fenológica.

La interfaz muestra:

- grados-día acumulados desde el pico;
- estado fenológico actual;
- grados-día restantes hasta 600 o 800 °Cd;
- fechas previstas o alcanzadas para ambos hitos;
- indicador gráfico de avance.

La descarga Excel incluye una hoja `Reloj_Fenologico`.

## Resultados operativos

La tabla y la descarga Excel utilizan nombres únicos para el modelo seleccionado:

- `EMERREL`;
- `EMERAC`;
- `TT_DESDE_PICO`;
- `Termoinhibida_Operativa`;
- `Umbral_Termoinhibicion_Operativo_C`;
- `FACTOR_DECAIMIENTO_OPERATIVO`;
- `DIAS_DESDE_PICO_OPERATIVO`;
- `Modelo_Operativo`;
- `Lag_Operativo_Dias`.

Las columnas internas del modelo alternativo se eliminan de la tabla y de la exportación operativa.

## Ejecución

```bash
python -m pip install -r requirements.txt
python update_meteo.py
streamlit run app.py
```

## Validación sintáctica

```bash
python -m py_compile app.py predweem_core.py visualizacion_pulsos.py \
  update_meteo.py update_meteo_core.py config_zavalla.py sitios_lolium.py
```

## Autoría

**PREDWEEM by Guillermo R. Chantre**

PREDWEEM es una herramienta de soporte para la toma de decisiones agronómicas.
