import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")

# Overpass API URL for OSM
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Step 1: Only get merged streets
def get_merged_streets_only(location, street_radius):
    lat, lng = map(float, location.split(','))

    osm_streets = get_osm_streets(lat, lng, street_radius)
    google_streets = get_google_streets(lat, lng, street_radius)

    merged_streets = {}
    for street_name, (street_lat, street_lng) in {**osm_streets, **google_streets}.items():
        key = (street_name, round(street_lat, 6), round(street_lng, 6))
        if key not in merged_streets:
            merged_streets[key] = (street_lat, street_lng)
    
    return list(merged_streets.keys())  # [(key_tuple, (lat, lng))]

def get_osm_streets(lat, lng, street_radius):
    """
    Uses OpenStreetMap (OSM) Overpass API to fetch nearby streets.
    Filters out unwanted road types and only includes valid street names.
    """
    overpass_query = f"""
    [out:json];
    (
      way(around:{street_radius},{lat},{lng})["highway"~"^(residential|living_street)$"];
    );
    out center;
    """

    response = requests.get(OVERPASS_URL, params={"data": overpass_query})

    if response.status_code == 200:
        json_data = response.json()
        elements = json_data.get("elements", [])

        streets = {}

        for element in elements:
            if "tags" in element and "name" in element["tags"]:
                street_name = element["tags"]["name"]
                center = element.get("center", {})

                street_lat = center.get("lat")
                street_lng = center.get("lon")

                if street_lat and street_lng:
                    streets[street_name] = (street_lat, street_lng)

        return streets
    return {}

def get_google_streets(lat, lng, street_radius):
    """
    Uses Google Places API to fetch valid street names.
    Filters out roads and unrelated results.
    """
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": street_radius,
        "key": google_api_key
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        json_data = response.json()
        if json_data.get("status") == "OK":
            places = json_data.get("results", [])
            streets = {}

            for place in places:
                address = place.get("vicinity", "")  # Use vicinity for local address
                clean_address = clean_street_name(address)

                if not clean_address or clean_address in streets:
                    continue  # Skip if no valid name or already added

                place_lat = place["geometry"]["location"]["lat"]
                place_lng = place["geometry"]["location"]["lng"]

                streets[clean_address] = (place_lat, place_lng)

            return streets
    return {}

def clean_street_name(address):
    """
    Extracts only valid street names while removing unwanted information.
    """
    parts = [part.strip() for part in address.split(',')]

    # Keywords indicating valid streets
    street_keywords = ["Street", "St", "Nagar", "Theru", "Ave"]

    # Extract valid street names
    valid_streets = [part for part in parts if any(keyword in part for keyword in street_keywords)]

    if valid_streets:
        return valid_streets[0]  # Return the first valid street found
    return None