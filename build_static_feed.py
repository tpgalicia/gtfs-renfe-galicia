# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
#     "tqdm",
# ]
# ///

from argparse import ArgumentParser
import csv
import json
import logging
import os
import shutil
import tempfile
import zipfile

import requests
from tqdm import tqdm


# Approximate bounding box for Galicia
BOUNDS = {"SOUTH": 41.820455, "NORTH": 43.937462, "WEST": -9.437256, "EAST": -6.767578}

FEEDS = {
    "general": "1098",
    "cercanias": "1130",
    "feve": "1131"
}


def is_in_bounds(lat: float, lon: float) -> bool:
    return (
        BOUNDS["SOUTH"] <= lat <= BOUNDS["NORTH"]
        and BOUNDS["WEST"] <= lon <= BOUNDS["EAST"]
    )


def get_stops_in_bounds(stops_file: str):
    with open(stops_file, "r", encoding="utf-8") as f:
        stops = csv.DictReader(f)

        for stop in stops:
            lat = float(stop["stop_lat"])
            lon = float(stop["stop_lon"])
            if is_in_bounds(lat, lon):
                yield stop


def get_trip_ids_for_stops(stoptimes_file: str, stop_ids: list[str]) -> list[str]:
    trip_ids: set[str] = set()

    with open(stoptimes_file, "r", encoding="utf-8") as f:
        stop_times = csv.DictReader(f)

        for stop_time in stop_times:
            if stop_time["stop_id"] in stop_ids:
                trip_ids.add(stop_time["trip_id"])

    return list(trip_ids)


def get_routes_for_trips(trips_file: str, trip_ids: list[str]) -> list[str]:
    route_ids: set[str] = set()

    with open(trips_file, "r", encoding="utf-8") as f:
        trips = csv.DictReader(f)

        for trip in trips:
            if trip["trip_id"] in trip_ids:
                route_ids.add(trip["route_id"])

    return list(route_ids)


def get_distinct_stops_from_stop_times(
    stoptimes_file: str, trip_ids: list[str]
) -> list[str]:
    stop_ids: set[str] = set()

    with open(stoptimes_file, "r", encoding="utf-8") as f:
        stop_times = csv.DictReader(f)

        for stop_time in stop_times:
            if stop_time["trip_id"] in trip_ids:
                stop_ids.add(stop_time["stop_id"])

    return list(stop_ids)


def get_last_stop_for_trips(
    stoptimes_file: str, trip_ids: list[str]
) -> dict[str, str]:
    trip_last: dict[str, str] = {}
    trip_last_seq: dict[str, int] = {}

    with open(stoptimes_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise Exception("Fuck you, screw you, fieldnames is None and you just get rekt")
        reader.fieldnames = [name.strip() for name in reader.fieldnames]

        for stop_time in reader:
            if stop_time["trip_id"] in trip_ids:
                trip_id = stop_time["trip_id"]
                if trip_last.get(trip_id, None) is None:
                    trip_last[trip_id] = ""
                    trip_last_seq[trip_id] = -1

                this_stop_seq = int(stop_time["stop_sequence"])
                if this_stop_seq > trip_last_seq[trip_id]:
                    trip_last_seq[trip_id] = this_stop_seq
                    trip_last[trip_id] = stop_time["stop_id"]

    return trip_last

def get_rows_by_ids(input_file: str, id_field: str, ids: list[str]) -> list[dict]:
    rows: list[dict] = []

    with open(input_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise Exception("Fuck you, screw you, fieldnames is None and you just get rekt")
        reader.fieldnames = [name.strip() for name in reader.fieldnames]

        for row in reader:
            if row[id_field].strip() in ids:
                rows.append(row)

    return rows

# First colour is background, second is text
SERVICE_COLOURS = {
    "REGIONAL": ("0658a9", "FFFFFF"),
    "REG.EXP.": ("0658a9", "FFFFFF"),

    "MD": ("EE7B2A", "000000"),
    "AVANT": ("EE7B2A", "000000"),

    "AVLO": ("9a0060", "01CFCA"),
    "AVE": ("9a0060", "FFFFFF"),
    "ALVIA": ("9a0060", "FFFFFF"),

    "INTERCITY": ("606060", "FFFFFF"),

    "TRENCELTA": ("00824A", "FFFFFF"),

    # Cercanías Ferrol-Ortigueira
    "C1": ("#EE20613", "FFFFFF")
}


def colour_route(route_short_name: str) -> tuple[str, str]:
    """
    Returns the colours to be used for a route from its short name.
    
    :param route_short_name: The routes.txt's route_short_name
    :return: A tuple containing the "route_color" (background) first and "route_text_color" (text) second
    :rtype: tuple[str, str]
    """
    
    if route_short_name.upper() in SERVICE_COLOURS:
        return SERVICE_COLOURS[route_short_name.upper()]
    
    print("Unknown route short name:", route_short_name)
    return ("000000", "FFFFFF")


if __name__ == "__main__":
    parser = ArgumentParser(
        description="Extract GTFS data for Galicia from Renfe GTFS feed."
    )
    parser.add_argument(
        "nap_apikey",
        type=str,
        help="NAP API Key (https://nap.transportes.gob.es/)"
    )
    parser.add_argument(
        "--osrm-url",
        type=str,
        help="OSRM server URL",
        default="http://localhost:5050",
        required=False,
    )
    parser.add_argument(
        "--debug",
        help="Enable debug logging",
        action="store_true"
    )

    args = parser.parse_args()

    try:
        osrm_check = requests.head(args.osrm_url, timeout=5)
        GENERATE_SHAPES = osrm_check.status_code < 500
    except requests.RequestException:
        GENERATE_SHAPES = False
        logging.warning("OSRM server is not reachable. Shape generation will be skipped.")


    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    for feed in FEEDS.keys():
        INPUT_GTFS_FD, INPUT_GTFS_ZIP = tempfile.mkstemp(suffix=".zip", prefix=f"renfe_galicia_in_{feed}_")
        INPUT_GTFS_PATH = tempfile.mkdtemp(prefix=f"renfe_galicia_in_{feed}_")
        OUTPUT_GTFS_PATH = tempfile.mkdtemp(prefix=f"renfe_galicia_out_{feed}_")
        OUTPUT_GTFS_ZIP = os.path.join(os.path.dirname(__file__), f"gtfs_renfe_galicia_{feed}.zip")

        FEED_URL = f"https://nap.transportes.gob.es/api/Fichero/download/{FEEDS[feed]}"

        logging.info(f"Downloading GTFS feed '{feed}'...")
        response = requests.get(FEED_URL, headers={"ApiKey": args.nap_apikey})
        with open(INPUT_GTFS_ZIP, "wb") as f:
            f.write(response.content)

        # Unzip the GTFS feed
        with zipfile.ZipFile(INPUT_GTFS_ZIP, "r") as zip_ref:
            zip_ref.extractall(INPUT_GTFS_PATH)

        STOPS_FILE = os.path.join(INPUT_GTFS_PATH, "stops.txt")
        STOP_TIMES_FILE = os.path.join(INPUT_GTFS_PATH, "stop_times.txt")
        TRIPS_FILE = os.path.join(INPUT_GTFS_PATH, "trips.txt")

        all_stops_applicable = [stop for stop in get_stops_in_bounds(STOPS_FILE)]
        logging.info(f"Total stops in Galicia: {len(all_stops_applicable)}")

        stop_ids = [stop["stop_id"] for stop in all_stops_applicable]
        trip_ids = get_trip_ids_for_stops(STOP_TIMES_FILE, stop_ids)

        route_ids = get_routes_for_trips(TRIPS_FILE, trip_ids)

        logging.info(f"Feed parsed successfully. Stops: {len(stop_ids)}, trips: {len(trip_ids)}, routes: {len(route_ids)}")
        if len(trip_ids) == 0 or len(route_ids) == 0:
            logging.warning(f"No trips or routes found for feed '{feed}'. Skipping...")
            shutil.rmtree(INPUT_GTFS_PATH)
            shutil.rmtree(OUTPUT_GTFS_PATH)
            continue

        # Copy agency.txt, calendar.txt, calendar_dates.txt as is
        for filename in ["agency.txt", "calendar.txt", "calendar_dates.txt"]:
            src_path = os.path.join(INPUT_GTFS_PATH, filename)
            dest_path = os.path.join(OUTPUT_GTFS_PATH, filename)
            if os.path.exists(src_path):
                shutil.copy(src_path, dest_path)
            else:
                logging.debug(f"File {filename} does not exist in the input GTFS feed.")

        # Write new stops.txt with the stops in any trip that passes through Galicia
        with open(
            os.path.join(os.path.dirname(__file__), "stop_overrides.json"),
            "r",
            encoding="utf-8",
        ) as f:
            stop_overrides_raw: list = json.load(f)
            stop_overrides = {
                item["stop_id"]: item
                for item in stop_overrides_raw
            }
            logging.debug(f"Loaded stop overrides for {len(stop_overrides)} stops.")

        distinct_stop_ids = get_distinct_stops_from_stop_times(
            STOP_TIMES_FILE, trip_ids
        )
        stops_in_trips = get_rows_by_ids(STOPS_FILE, "stop_id", distinct_stop_ids)
        for stop in stops_in_trips:
            stop["stop_code"] = stop["stop_id"]
            if stop_overrides.get(stop["stop_id"], None) is not None:
                for key, value in stop_overrides[stop["stop_id"]].items():
                    stop[key] = value

            if stop["stop_name"].startswith("Estación de tren "):
                stop["stop_name"] = stop["stop_name"][17:].strip()
                stop["stop_name"] = " ".join([
                    word.capitalize() for word in stop["stop_name"].split(" ") if word != "de"
                ])

        with open(
            os.path.join(OUTPUT_GTFS_PATH, "stops.txt"),
            "w",
            encoding="utf-8",
            newline="",
        ) as f:
            writer = csv.DictWriter(f, fieldnames=stops_in_trips[0].keys())
            writer.writeheader()
            writer.writerows(stops_in_trips)

        # Write new routes.txt with the routes that have trips in Galicia
        routes_in_trips = get_rows_by_ids(
            os.path.join(INPUT_GTFS_PATH, "routes.txt"), "route_id", route_ids
        )
        for route in routes_in_trips:
            route["route_color"], route["route_text_color"] = colour_route(
                route["route_short_name"]
            )
        with open(
            os.path.join(OUTPUT_GTFS_PATH, "routes.txt"),
            "w",
            encoding="utf-8",
            newline="",
        ) as f:
            writer = csv.DictWriter(f, fieldnames=routes_in_trips[0].keys())
            writer.writeheader()
            writer.writerows(routes_in_trips)

        # Write new trips.txt with the trips that pass through Galicia
        last_stop_in_trips = get_last_stop_for_trips(STOP_TIMES_FILE, trip_ids)

        trips_in_galicia = get_rows_by_ids(TRIPS_FILE, "trip_id", trip_ids)
        stops_by_id = {stop["stop_id"]: stop for stop in stops_in_trips}

        for tig in trips_in_galicia:
            if GENERATE_SHAPES:
                tig["shape_id"] = f"Shape_{tig['trip_id'][0:5]}"
            tig["trip_headsign"] = stops_by_id[last_stop_in_trips[tig["trip_id"]]]["stop_name"]
        with open(
            os.path.join(OUTPUT_GTFS_PATH, "trips.txt"),
            "w",
            encoding="utf-8",
            newline="",
        ) as f:
            writer = csv.DictWriter(f, fieldnames=trips_in_galicia[0].keys())
            writer.writeheader()
            writer.writerows(trips_in_galicia)

        # Write new stop_times.txt with the stop times for any trip that passes through Galicia
        stop_times_in_galicia = get_rows_by_ids(STOP_TIMES_FILE, "trip_id", trip_ids)
        with open(
            os.path.join(OUTPUT_GTFS_PATH, "stop_times.txt"),
            "w",
            encoding="utf-8",
            newline="",
        ) as f:
            writer = csv.DictWriter(f, fieldnames=stop_times_in_galicia[0].keys())
            writer.writeheader()
            writer.writerows(stop_times_in_galicia)

        logging.info("GTFS data for Galicia has been extracted successfully. Generate shapes for the trips...")

        if GENERATE_SHAPES:
            shape_ids_total = len(set(f"Shape_{trip_id[0:5]}" for trip_id in trip_ids))
            shape_ids_generated: set[str] = set()

            # Pre-load stops for quick lookup
            stops_dict = {stop["stop_id"]: stop for stop in stops_in_trips}

            # Group stop times by trip_id to avoid repeated file reads
            stop_times_by_trip: dict[str, list[dict]] = {}
            for st in stop_times_in_galicia:
                tid = st["trip_id"]
                if tid not in stop_times_by_trip:
                    stop_times_by_trip[tid] = []
                stop_times_by_trip[tid].append(st)

            OSRM_BASE_URL = f"{args.osrm_url}/route/v1/driving/"
            for trip_id in tqdm(trip_ids, total=shape_ids_total, desc="Generating shapes"):
                shape_id = f"Shape_{trip_id[0:5]}"
                if shape_id in shape_ids_generated:
                    continue

                stop_seq = stop_times_by_trip.get(trip_id, [])
                stop_seq.sort(key=lambda x: int(x["stop_sequence"].strip()))

                if not stop_seq:
                    continue

                final_shape_points = []
                i = 0
                while i < len(stop_seq) - 1:
                    stop_a = stops_dict[stop_seq[i]["stop_id"]]
                    lat_a, lon_a = float(stop_a["stop_lat"]), float(stop_a["stop_lon"])

                    if not is_in_bounds(lat_a, lon_a):
                        # S_i is out of bounds. Segment S_i -> S_{i+1} is straight line.
                        stop_b = stops_dict[stop_seq[i+1]["stop_id"]]
                        lat_b, lon_b = float(stop_b["stop_lat"]), float(stop_b["stop_lon"])

                        segment_points = [[lon_a, lat_a], [lon_b, lat_b]]
                        if not final_shape_points:
                            final_shape_points.extend(segment_points)
                        else:
                            final_shape_points.extend(segment_points[1:])
                        i += 1
                    else:
                        # S_i is in bounds. Find how many subsequent stops are also in bounds.
                        j = i + 1
                        while j < len(stop_seq):
                            stop_j = stops_dict[stop_seq[j]["stop_id"]]
                            if is_in_bounds(float(stop_j["stop_lat"]), float(stop_j["stop_lon"])):
                                j += 1
                            else:
                                break

                        # Stops from i to j-1 are in bounds.
                        if j > i + 1:
                            # We have at least two consecutive stops in bounds.
                            in_bounds_stops = stop_seq[i:j]
                            coordinates = []
                            for st in in_bounds_stops:
                                s = stops_dict[st["stop_id"]]
                                coordinates.append(f"{s['stop_lon']},{s['stop_lat']}")

                            coords_str = ";".join(coordinates)
                            osrm_url = f"{OSRM_BASE_URL}{coords_str}?overview=full&geometries=geojson"

                            segment_points = []
                            try:
                                response = requests.get(osrm_url, timeout=10)
                                if response.status_code == 200:
                                    data = response.json()
                                    if data.get("code") == "Ok":
                                        segment_points = data["routes"][0]["geometry"]["coordinates"]
                            except Exception:
                                pass

                            if not segment_points:
                                # Fallback to straight lines for this whole sub-sequence
                                segment_points = []
                                for k in range(i, j):
                                    s = stops_dict[stop_seq[k]["stop_id"]]
                                    segment_points.append([float(s["stop_lon"]), float(s["stop_lat"])])

                            if not final_shape_points:
                                final_shape_points.extend(segment_points)
                            else:
                                final_shape_points.extend(segment_points[1:])

                            i = j - 1 # Next iteration starts from S_{j-1}
                        else:
                            # Only S_i is in bounds, S_{i+1} is out.
                            # Segment S_i -> S_{i+1} is straight line.
                            stop_b = stops_dict[stop_seq[i+1]["stop_id"]]
                            lat_b, lon_b = float(stop_b["stop_lat"]), float(stop_b["stop_lon"])

                            segment_points = [[lon_a, lat_a], [lon_b, lat_b]]
                            if not final_shape_points:
                                final_shape_points.extend(segment_points)
                            else:
                                final_shape_points.extend(segment_points[1:])
                            i += 1

                shape_ids_generated.add(shape_id)

                with open(
                    os.path.join(OUTPUT_GTFS_PATH, "shapes.txt"),
                    "a",
                    encoding="utf-8",
                    newline="",
                ) as f:
                    fieldnames = [
                        "shape_id",
                        "shape_pt_lat",
                        "shape_pt_lon",
                        "shape_pt_sequence",
                    ]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)

                    if f.tell() == 0:
                        writer.writeheader()

                    for seq, point in enumerate(final_shape_points):
                        writer.writerow(
                            {
                                "shape_id": shape_id,
                                "shape_pt_lat": point[1],
                                "shape_pt_lon": point[0],
                                "shape_pt_sequence": seq,
                            }
                        )
        else:
            logging.info("Shape generation skipped as per user request.")

        # Create a ZIP archive of the output GTFS
        with zipfile.ZipFile(OUTPUT_GTFS_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(OUTPUT_GTFS_PATH):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, OUTPUT_GTFS_PATH)
                    zipf.write(file_path, arcname)

        logging.info(
            f"GTFS data from feed {feed} has been zipped successfully at {OUTPUT_GTFS_ZIP}."
        )
        os.close(INPUT_GTFS_FD)
        os.remove(INPUT_GTFS_ZIP)
        shutil.rmtree(INPUT_GTFS_PATH)
        shutil.rmtree(OUTPUT_GTFS_PATH)
