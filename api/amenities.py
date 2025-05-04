import os
import requests
from dotenv import load_dotenv
from geopy.distance import geodesic

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Match amenity categories to those in score.py
AMENITY_CATEGORIES = {
    "Hospital": ["hospital", "physiotherapist"],  # From score.py: "Hospital"
    "School": ["school"],                          # From score.py: "School"
    "College": ["university"],                     # From score.py: "College"
    "Shrine": ["hindu_temple", "church", "mosque"], # From score.py: "Shrine"
    "Junction": ["train_station"],                      # From score.py: "Junction"
    "Bus Stand": ["bus_station"],                  # From score.py: "Transports"
    "Entertainment": ["movie_theater", "stadium"],  # From score.py: "Entertainment"
    "Restaurant": ["restaurant","cafe"],                  # From score.py: "Restaurant"
    "Shops": ["supermarket", "grocery_or_supermarket","shopping_mall", "clothing_store", "convenience_store", "pharmacy"], # From score.py: "Shops"
    "Park": ["park"],                              # From score.py: "Park"
    "Gym": ["gym"],                                # From score.py: "Gym"
    "Gas Station": ["gas_station"],                # From score.py: "Gas Station"
    "Bank": ["bank"]                               # From score.py: "Bank"
}

def get_photo_url(photo_reference, max_width=800):
    """
    Constructs the photo URL from a photo reference using Google Places Photo API.
    """
    return (
        f"https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth={max_width}&photoreference={photo_reference}&key={api_key}"
    )

def get_place_details(place_id):
    """
    Calls the Place Details API to get richer data for a place.
    Returns None if request fails.
    """
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,rating,user_ratings_total,formatted_address,geometry,opening_hours,photos",
        "key": api_key
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json().get("result")
    except requests.exceptions.RequestException as e:
        print(f"Place Details API error for {place_id}: {e}")
        return None

def build_amenity_info(details, user_lat, user_lng):
    """
    Constructs a structured amenity dictionary with full place details.
    Supports multiple photos per amenity.
    """
    name = details.get("name")
    rating = details.get("rating", 0)
    reviews = details.get("user_ratings_total", 0)
    location = details.get("geometry", {}).get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")
    address = details.get("formatted_address", "")
    open_now = details.get("opening_hours", {}).get("open_now", None)

    if not lat or not lng:
        return None

    distance = int(geodesic((user_lat, user_lng), (lat, lng)).meters)

    # Collect multiple photo URLs
    photos = []
    for photo in details.get("photos", []):
        ref = photo.get("photo_reference")
        if ref:
            photos.append(get_photo_url(ref))

    return {
        "name": name,
        "rating": rating,
        "reviews": reviews,
        "distance": distance,
        "address": address,
        "open_now": open_now,
        "lat": lat,
        "lng": lng,
        "photos": photos
    }

def get_amenities_nearby(street_name, street_lat, street_lng, amenity_radius):
    """
    Fetches categorized amenities using Google Places NearbySearch and then enriches
    with Place Details to get more info and multiple photos.
    """
    print(f"\nFetching amenities around: {street_name} (Lat: {street_lat}, Lng: {street_lng})\n")
    amenities = {}

    for category, place_types in AMENITY_CATEGORIES.items():
        places = []
        for place_type in place_types:
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                "location": f"{street_lat},{street_lng}",
                "radius": amenity_radius,
                "type": place_type,
                "key": api_key
            }
            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                results = response.json().get("results", [])
                for result in results:
                    place_id = result.get("place_id")
                    if not place_id:
                        continue

                    # Call Place Details API for more info and photos
                    details = get_place_details(place_id)
                    if not details:
                        continue

                    amenity = build_amenity_info(details, street_lat, street_lng)
                    if amenity:
                        places.append(amenity)

            except requests.exceptions.RequestException as e:
                print(f"Error fetching amenities for {place_type}: {e}")
                continue

        if places:
            amenities[category] = places

    return amenities
