# PREDWEEM Zavalla — Selector binario sin lag / con lag

Implementación de PREDWEEM para **Zavalla, Santa Fe** (`-33.02157, -60.87930`) con selección supervisada entre dos hipótesis temporales de emergencia de *Lolium*:

- **modelo sin lag:** funciona inicialmente como alerta anticipada;
- **modelo con lag fijo:** desplaza la señal diaria después de la ANN y de los filtros biofísicos;
- **ninguno confirmado:** se activa cuando no existe emergencia en ninguna de las dos ventanas.

El sistema no estima lags locales intermedios. La decisión se limita al modelo sin lag o al modelo con el lag fijo configurado.

## Flujo operativo

1. La ANN calcula la emergencia diaria con `JD`, `TMAX`, `TMIN` y precipitación.
2. Se aplican choque hídrico, balance superficial, termoinhibición y latencia.
3. Se calcula simultáneamente `EMERREL_SIN_LAG` y `EMERREL_CON_LAG`.
4. Antes de la verificación a campo se muestran las dos curvas.
5. Al detectarse el primer pico sin lag, la aplicación solicita una inspección.
6. Si la primera inspección confirma emergencia, se selecciona el modelo sin lag y se oculta la curva con lag.
7. Si la primera inspección no detecta emergencia, se selecciona provisionalmente el modelo con lag fijo y se oculta la curva sin lag.
8. Una emergencia próxima a la ventana desplazada confirma el modelo con lag.
9. Si tampoco hay emergencia en la ventana con lag, el sistema rechaza ambos modelos y solicita revisar los parámetros.

## Estados

- `SIN_PICO_SIMULADO`
- `SIN_LAG_EN_EVALUACION`
- `VERIFICACION_1_PENDIENTE`
- `CON_LAG_PROVISIONAL`
- `SIN_LAG_CONFIRMADO`
- `CON_LAG_CONFIRMADO`
- `NINGUNO_CONFIRMADO`

## Meteorología

`update_meteo.py` genera `meteo_daily.csv` con:

- histórico modelado ECMWF IFS mediante Open-Meteo hasta ayer;
- pronóstico ECMWF IFS desde hoy;
- trazabilidad en `Fuente`, `TipoDato` y `Emision`.

La serie es información de modelo de grilla y no una observación meteorológica puntual de Zavalla.

## Ejecución

```bash
python -m pip install -r requirements.txt
python update_meteo.py
streamlit run app.py
```

## Datos de campo

La aplicación registra fecha, operario, plantas/m², cuadros positivos, cuadros totales y observaciones. El archivo puede descargarse y restaurarse en una sesión posterior.

En Streamlit Community Cloud, el sistema de archivos local puede ser efímero. Para uso productivo se recomienda conectar una base persistente o conservar los CSV/JSON descargados.

## Validación

```bash
python -m pytest -q
python -m py_compile app.py predweem_core.py selector_adaptativo.py update_meteo.py
```

## Autoría

**PREDWEEM by Guillermo R. Chantre**

Este repositorio no reemplaza el monitoreo a campo ni el criterio profesional agronómico.
