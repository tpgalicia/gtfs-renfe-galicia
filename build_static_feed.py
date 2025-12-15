# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests"
# ]
# ///

import csv
import json
import os
import shutil
import tempfile
import zipfile

import requests


# Approximate bounding box for Galicia
BOUNDS = {
    "SOUTH": 41.820455,
    "NORTH": 43.937462,
    "WEST": -9.437256,
    "EAST": -6.767578
}

FEED_URL = "https://ssl.renfe.com/gtransit/Fichero_AV_LD/google_transit.zip"


def get_stops_in_bounds(stops_file: str):
    with open(stops_file, 'r', encoding='utf-8') as f:
        stops = csv.DictReader(f)

        for stop in stops:
            lat = float(stop['stop_lat'])
            lon = float(stop['stop_lon'])
            if (BOUNDS['SOUTH'] <= lat <= BOUNDS['NORTH'] and
                    BOUNDS['WEST'] <= lon <= BOUNDS['EAST']):
                yield stop


def get_trip_ids_for_stops(stoptimes_file: str, stop_ids: list[str]) -> list[str]:
    trip_ids: set[str] = set()

    with open(stoptimes_file, 'r', encoding='utf-8') as f:
        stop_times = csv.DictReader(f)

        for stop_time in stop_times:
            if stop_time['stop_id'] in stop_ids:
                trip_ids.add(stop_time['trip_id'])

    return list(trip_ids)


def get_routes_for_trips(trips_file: str, trip_ids: list[str]) -> list[str]:
    route_ids: set[str] = set()

    with open(trips_file, 'r', encoding='utf-8') as f:
        trips = csv.DictReader(f)

        for trip in trips:
            if trip['trip_id'] in trip_ids:
                route_ids.add(trip['route_id'])

    return list(route_ids)


def get_distinct_stops_from_stop_times(stoptimes_file: str, trip_ids: list[str]) -> list[str]:
    stop_ids: set[str] = set()

    with open(stoptimes_file, 'r', encoding='utf-8') as f:
        stop_times = csv.DictReader(f)

        for stop_time in stop_times:
            if stop_time['trip_id'] in trip_ids:
                stop_ids.add(stop_time['stop_id'])

    return list(stop_ids)


def get_rows_by_ids(input_file: str, id_field: str, ids: list[str]) -> list[dict]:
    rows: list[dict] = []

    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row[id_field] in ids:
                rows.append(row)

    return rows


if __name__ == "__main__":
    INPUT_GTFS_ZIP = os.path.join(os.path.dirname(__file__), '..', 'gtfs_renfe.zip')
    INPUT_GTFS_PATH = tempfile.mkdtemp(prefix='renfe_galicia_in_')
    OUTPUT_GTFS_PATH = tempfile.mkdtemp(prefix='renfe_galicia_out_')
    OUTPUT_GTFS_ZIP = os.path.join(os.path.dirname(__file__), 'out')

    # Download the GTFS feed
    print("Downloading GTFS feed...")
    response = requests.get(FEED_URL)
    with open(INPUT_GTFS_ZIP, 'wb') as f:
        f.write(response.content)

    # Unzip the GTFS feed
    print("Unzipping GTFS feed...")
    with zipfile.ZipFile(INPUT_GTFS_ZIP, 'r') as zip_ref:
        zip_ref.extractall(INPUT_GTFS_PATH)

    STOPS_FILE = os.path.join(INPUT_GTFS_PATH, 'stops.txt')
    STOP_TIMES_FILE = os.path.join(INPUT_GTFS_PATH, 'stop_times.txt')
    TRIPS_FILE = os.path.join(INPUT_GTFS_PATH, 'trips.txt')

    all_stops_applicable = [stop for stop in get_stops_in_bounds(STOPS_FILE)]
    print(f"Total stops in Galicia: {len(all_stops_applicable)}")

    stop_ids = [stop['stop_id'] for stop in all_stops_applicable]
    trip_ids = get_trip_ids_for_stops(STOP_TIMES_FILE, stop_ids)
    print(f"Total trips in Galicia: {len(trip_ids)}")

    route_ids = get_routes_for_trips(TRIPS_FILE, trip_ids)
    print(f"Total routes in Galicia: {len(route_ids)}")

    # Copy agency.txt, calendar.txt, calendar_dates.txt as is
    for filename in ['agency.txt', 'calendar.txt', 'calendar_dates.txt']:
        src_path = os.path.join(INPUT_GTFS_PATH, filename)
        dest_path = os.path.join(OUTPUT_GTFS_PATH, filename)
        with open(src_path, 'r', encoding='utf-8') as src_file:
            with open(dest_path, 'w', encoding='utf-8') as dest_file:
                dest_file.write(src_file.read())

    # Write new stops.txt with the stops in any trip that passes through Galicia
    with open(os.path.join(os.path.dirname(__file__), "stop_overrides.json"), "r", encoding="utf-8") as f:
        stop_overrides = json.load(f)

    distinct_stop_ids = get_distinct_stops_from_stop_times(STOP_TIMES_FILE, trip_ids)
    stops_in_trips = get_rows_by_ids(STOPS_FILE, 'stop_id', distinct_stop_ids)
    for stop in stops_in_trips:
        stop['stop_code'] = stop['stop_id']
        if stop['stop_id'] in stop_overrides:
            for key, value in stop_overrides[stop['stop_id']].items():
                stop[key] = value

    with open(os.path.join(OUTPUT_GTFS_PATH, 'stops.txt'), 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=stops_in_trips[0].keys())
        writer.writeheader()
        writer.writerows(stops_in_trips)

    # Write new routes.txt with the routes that have trips in Galicia
    routes_in_trips = get_rows_by_ids(os.path.join(INPUT_GTFS_PATH, 'routes.txt'), 'route_id', route_ids)
    with open(os.path.join(OUTPUT_GTFS_PATH, 'routes.txt'), 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=routes_in_trips[0].keys())
        writer.writeheader()
        writer.writerows(routes_in_trips)

    # Write new trips.txt with the trips that pass through Galicia
    trips_in_galicia = get_rows_by_ids(TRIPS_FILE, 'trip_id', trip_ids)
    for tig in trips_in_galicia:
        tig['shape_id'] = f"Shape_{tig['trip_id'][0:5]}"
    with open(os.path.join(OUTPUT_GTFS_PATH, 'trips.txt'), 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=trips_in_galicia[0].keys())
        writer.writeheader()
        writer.writerows(trips_in_galicia)

    # Write new stop_times.txt with the stop times for any trip that passes through Galicia
    stop_times_in_galicia = get_rows_by_ids(STOP_TIMES_FILE, 'trip_id', trip_ids)
    with open(os.path.join(OUTPUT_GTFS_PATH, 'stop_times.txt'), 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=stop_times_in_galicia[0].keys())
        writer.writeheader()
        writer.writerows(stop_times_in_galicia)

    print("GTFS data for Galicia has been extracted successfully.")
    print("Beginning to generate shapes for the trips...")

    shape_ids_total = len(set(f"Shape_{trip_id[0:5]}" for trip_id in trip_ids))
    shape_ids_generated: set[str] = set()

    OSRM_BASE_URL = "http://localhost:5050/route/v1/driving/"
    for trip_id in trip_ids:
        shape_id = f"Shape_{trip_id[0:5]}"
        if shape_id in shape_ids_generated:
            continue

        print(f"Generating shape {shape_id} ({len(shape_ids_generated)+1}/{shape_ids_total})")

        stop_seq = get_rows_by_ids(STOP_TIMES_FILE, 'trip_id', [trip_id])
        stop_seq.sort(key=lambda x: int(x['stop_sequence']))

        coordinates = []
        for stop_time in stop_seq:
            stop = get_rows_by_ids(STOPS_FILE, 'stop_id', [stop_time['stop_id']])[0]
            coordinates.append(f"{stop['stop_lon']},{stop['stop_lat']}")

        coords_str = ";".join(coordinates)
        osrm_url = f"{OSRM_BASE_URL}{coords_str}?overview=full&geometries=geojson"
        response = requests.get(osrm_url)
        data = response.json()

        line_path = data['routes'][0]['geometry']
        shape_points = line_path['coordinates']
        shape_ids_generated.add(shape_id)

        with open(os.path.join(OUTPUT_GTFS_PATH, 'shapes.txt'), 'a', encoding='utf-8', newline='') as f:
            fieldnames = ['shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence']
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if f.tell() == 0:
                writer.writeheader()

            for seq, point in enumerate(shape_points):
                writer.writerow({
                    'shape_id': shape_id,
                    'shape_pt_lat': point[1],
                    'shape_pt_lon': point[0],
                    'shape_pt_sequence': seq
                })

    # Create a ZIP archive of the output GTFS
    output_zip_path = os.path.join(os.path.dirname(__file__), 'renfe_galicia_gtfs.zip')
    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(OUTPUT_GTFS_PATH):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, OUTPUT_GTFS_PATH)
                zipf.write(file_path, arcname)

    print(f"GTFS data for Galicia has been zipped successfully at {output_zip_path}.")
    os.remove(INPUT_GTFS_ZIP)
    shutil.rmtree(INPUT_GTFS_PATH)
    shutil.rmtree(OUTPUT_GTFS_PATH)
