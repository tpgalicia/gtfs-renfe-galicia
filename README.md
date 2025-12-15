# Generador de GTFS Renfe Galicia

Este repositorio contiene un script para extraer un feed GTFS estático para los servicios de Renfe en Galicia, España. El script descarga los datos oficiales del portal de Open Data de Renfe, extrae los viajes con paradas en Galicia y genera un nuevo feed GTFS con esta información. Adicionalmente, genera las formas de los viajes utilizando un servidor OSRM local con datos de OpenStreetMap (Geofabrik).

## Requisitos

- Python 3.12 o superior y `requests`. Con [uv](https://docs.astral.sh/uv) no es necesario instalar dependencias manualmente.
- Docker y Docker Compose. Alternativamente, Rancher, Podman u otros gestores compatibles con Dockerfile y archivos docker-compose.yml.

## Uso

1. Clona este repositorio:

   ```bash
   git clone https://github.com/tpgalicia/gtfs-renfe-galicia.git
   cd gtfs-renfe-galicia
   ```

2. Inicia el servidor OSRM local con datos de OpenStreetMap para Galicia y perfil específico para trenes. La primera vez puede tardar varios minutos en arrancar ya que tiene que preprocesar los datos:

   ```bash
    docker-compose up -d
    ```

3. Ejecutar el script para generar el feed GTFS estático:

   ```bash
   uv run build_static_feed.py
   ```

El feed GTFS generado se guardará en `renfe_galicia_gtfs.zip`.

## Notas

- Asegúrate de que el servidor OSRM esté en funcionamiento antes de ejecutar el script, en el puerto 5050.
- El script filtra los viajes para incluir solo aquellos con paradas en Galicia, basándose en las coordenadas geográficas de las estaciones.
- Las formas de los viajes se generan utilizando el servidor OSRM local para obtener rutas entre las paradas.
- Solo se utiliza el feed de Renfe Operadora, excluyendo (por el momento) los servicios de Cercanías Ancho Métrico de la línea Ferrol-Ortigueira.

## Licencia

Este proyecto está cedido como software libre bajo licencia EUPL v1.2 o superior. Más información en el archivo [`LICENCE`](LICENCE) o en [Interoperable Europe](https://interoperable-europe.ec.europa.eu/collection/eupl).

Los datos GTFS originales son propiedad de Renfe Operadora, cedidos bajo licencia [Creative Commons Reconocimiento 4.0 Internacional (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) o según se indica en [su portal de Datos Abiertos](https://data.renfe.com/legal).
