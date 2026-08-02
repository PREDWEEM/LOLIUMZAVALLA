# PREDWEEM LOLIUM — Modelo operativo automático por localidad

Aplicación multisitio para simular la emergencia de *Lolium* con una política de modelo definida previamente para cada localidad.

## Meteorología de Zavalla

La prioridad por variable es:

1. SMN Rosario Aero 87480;
2. NOAA NCEI cuando esté disponible;
3. Open-Meteo ECMWF IFS Archive para completar faltantes;
4. Open-Meteo ECMWF IFS Forecast desde el día actual.

El comando operativo único es:

```bash
python update_meteo.py
```

Los valores negativos de precipitación observada se consideran códigos inválidos y se reemplazan con la fuente siguiente.

## Ejecución

```bash
python -m pip install -r requirements.txt
python update_meteo.py
streamlit run app.py
```

## Autoría

**PREDWEEM by Guillermo R. Chantre**
