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

Cada sitio utiliza una copia exacta de `meteo_daily.csv` proveniente de su repositorio geográfico público:

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

`update_meteo.py` copia los archivos byte por byte, sin combinar fuentes, cambiar columnas ni volver a serializar el CSV. El workflow diario verifica tamaño y hash SHA-256 antes de guardar los cambios.

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
  update_meteo.py config_zavalla.py sitios_lolium.py
```

## Autoría

**PREDWEEM by Guillermo R. Chantre**

PREDWEEM es una herramienta de soporte para la toma de decisiones agronómicas.
