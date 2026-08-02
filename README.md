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

Los sitios distintos de Zavalla conservan copias exactas de `meteo_daily.csv` provenientes de sus repositorios geográficos.

Para Zavalla, la prioridad por variable es:

1. SMN Rosario Aero 87480;
2. NOAA NCEI como respaldo observado, cuando esté disponible;
3. Open-Meteo ECMWF IFS Archive para completar faltantes;
4. Open-Meteo ECMWF IFS Forecast desde el día actual.

El comando operativo único es:

```bash
python update_meteo.py
```

Ese comando descarta códigos negativos de precipitación observada y permite que la fuente siguiente complete el dato.

## Reloj de grados-día fenológico

El reloj se inicia en el primer pico del modelo operativo y acumula `GD_Tb2` hasta la fecha meteorológica vigente.

Los hitos son:

- **600 °Cd:** inicio de la ventana de máxima susceptibilidad;
- **800 °Cd:** límite operativo de la ventana fenológica.

## Ejecución

```bash
python -m pip install -r requirements.txt
python update_meteo.py
streamlit run app.py
```

## Autoría

**PREDWEEM by Guillermo R. Chantre**

PREDWEEM es una herramienta de soporte para la toma de decisiones agronómicas.
