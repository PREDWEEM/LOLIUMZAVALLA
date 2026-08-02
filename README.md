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

Wmax, exponente Kr, termoinhibición, latencia, umbrales de lluvia, decaimiento y lag operativo permanecen fijados por la calibración específica de cada localidad.

## Meteorología de Zavalla: estructura híbrida

Zavalla ya no utiliza ECMWF IFS como única fuente histórica. La actualización diaria aplica esta prioridad **por variable**:

1. **SMN WIS2 — Rosario Aero 87480:** observaciones SYNOP de temperatura y precipitación disponibles.
2. **NOAA NCEI GSOD — estación 87480099999:** respaldo observado derivado de ISD.
3. **Open-Meteo ECMWF IFS Archive:** completa únicamente los huecos que continúen sin observación.
4. **Open-Meteo ECMWF IFS Forecast:** se utiliza desde el día actual y para los días futuros.

La serie conserva las columnas operativas:

```text
Fecha,TMAX,TMIN,Prec,Fuente,TipoDato,CalidadDato,Emision
```

y agrega trazabilidad independiente:

```text
Fuente_TMAX,Fuente_TMIN,Fuente_Prec
```

Por lo tanto, un mismo día puede combinar temperatura observada por SMN con precipitación respaldada por NOAA. Cuando ninguna fuente observada cubre una variable, esa variable queda identificada explícitamente como `OPEN_METEO_ECMWF_IFS_ARCHIVE_FALLBACK`.

Los demás sitios continúan usando copias exactas de `meteo_daily.csv` provenientes de sus repositorios geográficos:

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

La serie híbrida de Zavalla se guarda en:

```text
data/meteo_sitios/zavalla.csv
meteo_daily.csv
```

## Actualización automática

El workflow `.github/workflows/update_meteo.yml` se ejecuta:

- diariamente a las 07:30 de Argentina;
- manualmente mediante `workflow_dispatch`;
- cuando cambia el código de actualización o sus pruebas.

Antes de guardar datos, ejecuta pruebas de prioridad, valida continuidad diaria, valores nulos, coherencia `TMAX ≥ TMIN`, precipitación no negativa y presencia del pronóstico del día actual.

Si SMN o NOAA están temporalmente indisponibles, el proceso continúa con las siguientes fuentes de la jerarquía y registra el diagnóstico en:

```text
data/estado_actualizacion_meteo.json
```

## Sin recuentos de campo

Se eliminaron del flujo operativo:

- formulario de inspección;
- carga y restauración de conteos;
- historial de plantas por metro cuadrado;
- puntos de campo sobre la gráfica;
- selección adaptativa mediante observaciones;
- exportación de inspecciones y estado del selector.

## Reloj de grados-día fenológico

El reloj se inicia en el primer pico del modelo operativo y acumula `GD_Tb2` hasta la fecha meteorológica vigente.

Los hitos son:

- **600 °Cd:** inicio de la ventana de máxima susceptibilidad;
- **800 °Cd:** límite operativo de la ventana fenológica.

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

## Ejecución

```bash
python -m pip install -r requirements.txt
python update_meteo.py
streamlit run app.py
```

## Pruebas y validación sintáctica

```bash
python -m pytest tests/test_update_meteo.py -q
python -m py_compile app.py predweem_core.py visualizacion_pulsos.py \
  update_meteo.py config_zavalla.py sitios_lolium.py
```

## Autoría

**PREDWEEM by Guillermo R. Chantre**

PREDWEEM es una herramienta de soporte para la toma de decisiones agronómicas.
