import os
import requests 
import numpy as np 
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Amenity category weights (importance for amenities scoring)
AMENITY_WEIGHTS = {
    "Hospital": 13,
    "School": 12,
    "College": 11,         # Newly added
    "Shrine": 10,
    "Junction": 9,
    "Bus Stand": 8,
    "Entertainment": 7,
    "Restaurant": 6,
    "Shops": 5,
    "Park": 4,
    "Gym": 3,
    "Gas Station": 2,
    "Bank": 1
}


# Criteria weights for TOPSIS (amenities, air quality, noise)
CRITERIA_WEIGHTS = {
    "AmenityScore": 0.5,   # Importance of amenities
    "AirQuality": 0.3,     # Importance of air quality
    "NoiseLevel": 0.2      # Importance of noise pollution
}

# Whether each criterion is a "benefit" or "cost"
CRITERIA_TYPE = {
    "AmenityScore": "benefit",   # More amenities = better
    "AirQuality": "benefit",     # Higher air quality = better (we'll adjust AQI scale)
    "NoiseLevel": "cost"         # Lower noise = better
}

# Noise weights per amenity category
NOISE_WEIGHTS = {
    "Transports": 3.0,    # High noise
    "Shops": 2.0,         # Medium noise
    "Entertainment": 2.5, # Medium noise
    "Restaurants": 1.5,   # Moderate noise
    "Shrines": 0.5,       # Low noise
    "Parks": 0.3          # Very low noise
}

def calculate_street_score(amenities, custom_weights=None):
    """
    Calculates an amenities-based score for a single street using TOPSIS logic.
    Accepts optional custom weights to override defaults.
    
    :param amenities: Dictionary of nearby places categorized.
    :param custom_weights: Optional dict of amenity weights from user preferences.
    :return: float (score out of 10)
    """
    criteria_values = []
    weights = []

    # Use custom weights if provided, else default ones
    weights_dict = custom_weights if custom_weights else AMENITY_WEIGHTS

    for category in weights_dict.keys():
        value = len(amenities.get(category, []))
        criteria_values.append(value)
        weights.append(weights_dict.get(category, AMENITY_WEIGHTS[category]))  # fallback to default

    criteria_values = np.array(criteria_values, dtype=float)
    weights = np.array(weights, dtype=float)

    norm_denominator = np.sqrt(np.sum(criteria_values ** 2))
    if norm_denominator == 0:
        return 0.0

    normalized_values = criteria_values / norm_denominator
    weighted_normalized_values = normalized_values * weights

    ideal_best = np.max(weighted_normalized_values)
    ideal_worst = np.min(weighted_normalized_values)

    distance_to_best = np.sqrt(np.sum((weighted_normalized_values - ideal_best) ** 2))
    distance_to_worst = np.sqrt(np.sum((weighted_normalized_values - ideal_worst) ** 2))

    if (distance_to_best + distance_to_worst) == 0:
        topsis_score = 0
    else:
        topsis_score = distance_to_worst / (distance_to_best + distance_to_worst)

    normalized_score = round(topsis_score * 10, 2)
    return normalized_score

def calculate_noise_level(amenities):
    """
    Estimates noise pollution level based on nearby amenities.
    Returns a noise score (0-10 scale) and a label (Low/Medium/High).
    
    :param amenities: Dictionary of nearby places categorized.
    :return: str ("Low", "Medium", "High")
    """
    total_noise = 0
    max_noise = sum(NOISE_WEIGHTS.values()) * 10  # Assuming max 10 places per category

    for category, places in amenities.items():
        weight = NOISE_WEIGHTS.get(category, 1.0)
        total_noise += weight * len(places)

    # Normalize noise level to 0-10 scale
    noise_score = (total_noise / max_noise) * 10
    noise_score = round(noise_score, 2)

    # Classify noise level
    if noise_score >= 7:
        noise_label = "High"
    elif noise_score >= 4:
        noise_label = "Medium"
    else:
        noise_label = "Low"

    return noise_label


def get_air_quality(lat, lng):
    """
    Fetches Air Quality Index (AQI) data from Google Air Quality API.
    Returns AQI score, category name, and hex color code.
    """
    if not GOOGLE_API_KEY:
        return None, "API key missing", None

    url = f"https://airquality.googleapis.com/v1/currentConditions:lookup?key={GOOGLE_API_KEY}"

    payload = {
        "location": {
            "latitude": lat,
            "longitude": lng
        }
    }

    headers = {
        "Content-Type": "application/json"
    }

    def rgb_to_hex(color_dict):
        """Convert a dict with RGB float values (0–1) to hex."""
        r = int(color_dict.get("red", 0) * 255)
        g = int(color_dict.get("green", 0) * 255)
        b = int(color_dict.get("blue", 0) * 255)
        return "#{:02X}{:02X}{:02X}".format(r, g, b)

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        if "indexes" in data and data["indexes"]:
            aqi_data = next((idx for idx in data["indexes"] if idx["code"].lower() == "uaqi"), data["indexes"][0])

            aqi = int(aqi_data.get("aqi", 0))
            category_full = aqi_data.get("category", "Unknown")
            category = category_full.split()[0] if isinstance(category_full, str) else "Unknown"

            
            # Convert RGB dict to hex string
            color_rgb = aqi_data.get("color", {})
            color_hex = rgb_to_hex(color_rgb) if isinstance(color_rgb, dict) else "#999999"

            return aqi, category, color_hex

        return None, "No data", None

    except requests.RequestException:
        return None, "Error fetching AQI", None