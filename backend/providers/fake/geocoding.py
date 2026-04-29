"""Deterministic in-memory `GeocodingProvider`.

A small canned table of well-known landmarks plus a hash-based
fallback so any address resolves to *some* lat/lon pair. Tests get
predictable round-trips without a Google Maps key."""

from __future__ import annotations

import hashlib

from backend.providers.geocoding import GeocodedLocation, GeocodingProvider

_KNOWN: dict[str, GeocodedLocation] = {
    "boulder, co": GeocodedLocation(
        lat=40.0150,
        lon=-105.2705,
        formatted_address="Boulder, CO, USA",
        country="US",
        administrative_area="CO",
        locality="Boulder",
        postal_code="80302",
        place_id="fake-boulder",
    ),
    "london, uk": GeocodedLocation(
        lat=51.5074,
        lon=-0.1278,
        formatted_address="London, United Kingdom",
        country="GB",
        administrative_area="Greater London",
        locality="London",
        postal_code="WC2N 5DU",
        place_id="fake-london",
    ),
    "cape town, za": GeocodedLocation(
        lat=-33.9249,
        lon=18.4241,
        formatted_address="Cape Town, South Africa",
        country="ZA",
        administrative_area="Western Cape",
        locality="Cape Town",
        place_id="fake-cape-town",
    ),
}


class FakeGeocodingProvider:
    """Lookup is case-insensitive; unknown queries get a deterministic
    pseudo-coordinate so tests can still round-trip them."""

    name: str = "fake-geocoding"

    async def geocode(self, address: str) -> GeocodedLocation:
        key = address.strip().lower()
        if key in _KNOWN:
            return _KNOWN[key]
        return _hashed_location(address)

    async def reverse(self, lat: float, lon: float) -> GeocodedLocation:
        for loc in _KNOWN.values():
            if abs(loc.lat - lat) < 0.5 and abs(loc.lon - lon) < 0.5:
                return loc
        return GeocodedLocation(
            lat=lat,
            lon=lon,
            formatted_address=f"({lat:.4f}, {lon:.4f})",
            country="ZZ",
            place_id=f"fake-{lat:.4f}-{lon:.4f}",
        )


def _hashed_location(address: str) -> GeocodedLocation:
    digest = hashlib.sha256(address.encode("utf-8")).digest()
    # Map the first 4 bytes to lat in [-60, 60], next 4 to lon in [-180, 180].
    lat_raw = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF  # 0..1
    lon_raw = int.from_bytes(digest[4:8], "big") / 0xFFFFFFFF
    lat = -60.0 + lat_raw * 120.0
    lon = -180.0 + lon_raw * 360.0
    return GeocodedLocation(
        lat=lat,
        lon=lon,
        formatted_address=address,
        country="ZZ",
        place_id=f"fake-hashed-{digest[:4].hex()}",
    )


_: GeocodingProvider = FakeGeocodingProvider()
