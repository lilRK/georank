import os, json, asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from api.geocode import geocode_address
from api.places import get_merged_streets_only
from api.amenities import get_amenities_nearby
from score import calculate_street_score, calculate_noise_level, get_air_quality

# Load environment variables
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Initialize FastAPI app
app = FastAPI()

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint: /search
@app.post("/search")
async def search(request: Request):
    data = await request.json()
    address = data.get("address")
    lat, lng = geocode_address(address)

    if lat is None or lng is None:
        return JSONResponse(content={"error": "Unable to geocode the address."}, status_code=400)

    aqi, category, color = get_air_quality(lat, lng)

    return {
        "address": address,
        "lat": lat,
        "lng": lng,
        "aqi": aqi,
        "aqi_desc": category,
        "aqi_color": color
    }

# Endpoint: /streets with real-time SSE progress
@app.post("/streets")
async def streets(request: Request):
    data = await request.json()
    lat = data.get("lat")
    lng = data.get("lng")
    street_radius = int(data.get("street_radius", 1000))
    amenity_radius = int(data.get("amenity_radius", 400))
    weights = data.get("weights", {})
    location = f"{lat},{lng}"

    merged_streets = get_merged_streets_only(location, street_radius)
    total_streets = len(merged_streets)

    async def event_stream():
        if total_streets == 0:
            yield f"data: {json.dumps({'progress': 100, 'streets': []})}\n\n"
            return

        scored_streets = []
        yield f"data: {json.dumps({'count': total_streets})}\n\n"
        for idx, (street_name, s_lat, s_lng) in enumerate(merged_streets):
            amenities = get_amenities_nearby(street_name, s_lat, s_lng, amenity_radius)
            score = calculate_street_score(amenities, custom_weights=weights)
            noise = calculate_noise_level(amenities)

            scored_streets.append((street_name, s_lat, s_lng, score, noise, amenities))

            # Calculate and yield progress update
            progress = int(((idx + 1) / total_streets) * 100)
            yield f"data: {json.dumps({'progress': progress})}\n\n"
            await asyncio.sleep(0)  # Allow other tasks to run

        # Final full street data
        scored_streets.sort(key=lambda x: x[3], reverse=True)
        streets_data = [
            {
                "name": s,
                "latitude": s_lat,
                "longitude": s_lng,
                "score": score,
                "noise": noise,
                "amenities": amenities
            }
            for s, s_lat, s_lng, score, noise, amenities in scored_streets
        ]
        yield f"data: {json.dumps({'streets': streets_data})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# Endpoint: /update-weights
@app.post("/update-weights")
async def update_weights(request: Request):
    data = await request.json()
    preferences = data.get("preferences", [])

    max_score = len(preferences)
    weights = {amenity: max_score - idx for idx, amenity in enumerate(preferences)}

    return {"weights": weights}
