# Use a multi-stage build to download necessary files
FROM alpine/curl AS downloader

RUN curl -L https://download.geofabrik.de/europe/spain/galicia-latest.osm.pbf -o /galicia-latest.osm.pbf
RUN curl -L https://raw.githubusercontent.com/railnova/osrm-train-profile/refs/heads/master/basic.lua -o /opt/train.lua

FROM osrm/osrm-backend

# Copy the downloaded OSM file from the downloader stage
COPY --from=downloader /galicia-latest.osm.pbf /data/galicia-latest.osm.pbf
COPY --from=downloader /opt/train.lua /opt/train.lua

# Extract the map data using osrm-train-profile (by Railnova)
RUN osrm-extract -p /opt/train.lua /data/galicia-latest.osm.pbf

# Prepare the map data for routing
RUN osrm-partition /data/galicia-latest.osrm
RUN osrm-customize /data/galicia-latest.osrm

# Expose the OSRM server port
EXPOSE 5000

# Start the OSRM server
CMD ["osrm-routed", "--algorithm", "mld", "/data/galicia-latest.osrm"]

