# Generador de GTFS Renfe Galicia

Este repositorio contiene un script para extraer feeds GTFS estático para los servicios de Renfe en Galicia, España; usando los tres feeds disponibles (general, cercanías y FEVE). El script descarga los datos oficiales del Punto de Acceso Nacional (NAP) de España, extrae los viajes con paradas en Galicia y genera nuevos feeds GTFS con esta información. Adicionalmente, genera las formas de los viajes utilizando un servidor OSRM local con datos de OpenStreetMap (Geofabrik).

## Cambios que se realizan

1. Recortar los viajes para incluir solo aquellos con al menos una parada en Galicia.
2. Añadir headsigns a los viajes usando la última parada (como aparece en los letreros de los trenes).
3. Generar las formas de los viajes utilizando un servidor OSRM local con datos de OpenStreetMap para Galicia y un perfil específico para trenes.
4. Corregir algunos nombres y posiciones de estaciones para que sean fieles a la realidad.
5. Añadir colores a las rutas basándose en colores oficiales actuales y pasados de Renfe: naranja para Media Distancia, rojo Cercanías, verde en Trencelta, morado para regionales y AVE, 

## Requisitos

- Python 3.12 o superior y `requests`. Con [uv](https://docs.astral.sh/uv) no es necesario instalar dependencias manualmente.
- Clave API del Punto de Acceso Nacional (NAP) de España. Se puede obtener en su portal: <https://nap.transportes.gob.es> registrándose como consumidor de manera gratuita.
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
   uv run build_static_feed.py <NAP API KEY>
   ```

Los feeds GTFS generados se guardarán en `gtfs_renfe_galicia_{feed}.zip` donde `feed` puede ser `general`, `cercanias` o `feve`.

## Notas

- Asegúrate de que el servidor OSRM esté en funcionamiento antes de ejecutar el script, en el puerto 5050.
- El script filtra los viajes para incluir solo aquellos con paradas en Galicia, basándose en las coordenadas geográficas de las estaciones.
- Las formas de los viajes se generan utilizando el servidor OSRM local para obtener rutas entre las paradas.

## Licencia

Este proyecto está cedido como software libre bajo licencia EUPL v1.2 o superior. Más información en el archivo [`LICENCE`](LICENCE) o en [Interoperable Europe](https://interoperable-europe.ec.europa.eu/collection/eupl).

Los datos GTFS originales son propiedad de Renfe Operadora, cedidos bajo la [licencia de uso libre del NAP](https://nap.transportes.gob.es/licencia-datos).