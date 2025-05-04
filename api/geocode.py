import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")

def geocode_address(address, region="IN"):
    """
    Converts an address into latitude and longitude using Google Geocoding API.
    Region bias set to India (IN) by default.
    """
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    full_address = f"{address}, India"  # Adding country context to improve accuracy
    params = {
        "address": full_address,
        "region": region,
        "key": google_api_key
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        json_data = response.json()
        if json_data["status"] == "OK":
            location = json_data["results"][0]["geometry"]["location"]
            return location["lat"], location["lng"]
        else:
            print(f"Error: {json_data['status']}")
            return None, None
    else:
        print(f"HTTP Error: {response.status_code}")
        return None, None
