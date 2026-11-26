"""Curated, source-checked accommodation recommendations; no network on render."""
import json
from pathlib import Path

with (Path(__file__).parent / 'data' / 'hotel_recommendations.json').open(encoding='utf-8') as source:
    HOTEL_CATALOG = json.load(source)


def get_hotels(slug, static_folder):
    """Resolve local photographs, keeping every property usable without an image."""
    hotels = []
    for entry in HOTEL_CATALOG['destinations'].get(slug, []):
        hotel = dict(entry, image=None, image_large=None)
        photo = entry.get('photo')
        if photo:
            image = f"hotels/{photo['asset_base']}-640.webp"
            larger = f"hotels/{photo['asset_base']}-960.webp"
            if (Path(static_folder) / image).is_file():
                hotel['image'] = image
                if (Path(static_folder) / larger).is_file():
                    hotel['image_large'] = larger
        hotels.append(hotel)
    return hotels
