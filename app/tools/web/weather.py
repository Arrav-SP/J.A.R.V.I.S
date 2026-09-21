"""Real-time weather retrieval tool for JARVIS.

Fetches live meteorological telemetry and forecasts using free, zero-key APIs
(wttr.in with Open-Meteo fallback).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from app.tools.schemas import BaseTool, ToolDefinition, ToolParameter

logger = logging.getLogger("jarvis.tools.weather")


# WMO Weather interpretation codes (WW) used by Open-Meteo
WMO_WEATHER_CODES: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


@dataclass
class WeatherReport:
    """Structured meteorological report."""

    location: str
    country: str
    temperature_c: float
    feels_like_c: float
    condition: str
    humidity_percent: int
    wind_speed_kmh: float
    precipitation_mm: float
    daily_max_c: float
    daily_min_c: float
    source: str

    def to_summary(self) -> str:
        """Format report into a natural, concise conversational summary."""
        loc = f"{self.location}, {self.country}" if self.country else self.location
        return (
            f"Current weather in {loc}: {self.temperature_c:.1f}°C (feels like {self.feels_like_c:.1f}°C), "
            f"{self.condition}. Humidity: {self.humidity_percent}%, Wind: {self.wind_speed_kmh:.1f} km/h. "
            f"Today's high is {self.daily_max_c:.1f}°C and low is {self.daily_min_c:.1f}°C."
        )


class WeatherTool(BaseTool):
    """Fetches real-time weather and forecasts for any worldwide location."""

    def __init__(self, timeout_seconds: float = 6.0) -> None:
        self.timeout_seconds = timeout_seconds

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_weather",
            description="Fetch current live weather conditions and daily forecast for a given city or location.",
            category="web",
            parameters=[
                ToolParameter(
                    name="location",
                    type_name="string",
                    description="City or region name (e.g. 'Vellore', 'Chennai', 'London', 'New York').",
                    required=True,
                )
            ],
        )

    def run(self, location: str = "Vellore", **kwargs: Any) -> Dict[str, Any]:
        """Fetch live weather, trying wttr.in first with Open-Meteo fallback."""
        clean_loc = location.strip()
        if not clean_loc:
            clean_loc = "Vellore"

        # 1. Try wttr.in (instantaneous JSON)
        try:
            return self._fetch_wttr(clean_loc)
        except Exception as err:
            logger.warning("wttr.in lookup failed for '%s': %s. Falling back to Open-Meteo.", clean_loc, err)

        # 2. Try Open-Meteo
        try:
            return self._fetch_open_meteo(clean_loc)
        except Exception as err:
            logger.error("Open-Meteo lookup failed for '%s': %s", clean_loc, err)
            raise RuntimeError(f"Unable to retrieve weather for '{clean_loc}'. All weather endpoints failed.") from err

    def _fetch_wttr(self, location: str) -> Dict[str, Any]:
        """Query wttr.in JSON endpoint."""
        url = f"https://wttr.in/{urllib.parse.quote(location)}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        current = data["current_condition"][0]
        weather = data.get("weather", [{}])[0]

        # Extract nearest area
        area = data.get("nearest_area", [{}])[0]
        city_name = area.get("areaName", [{}])[0].get("value", location)
        country = area.get("country", [{}])[0].get("value", "")

        desc = current.get("weatherDesc", [{}])[0].get("value", "Clear")
        temp_c = float(current.get("temp_C", 0.0))
        feels_c = float(current.get("FeelsLikeC", temp_c))
        humidity = int(current.get("humidity", 0))
        wind_kmh = float(current.get("windspeedKmph", 0.0))
        precip = float(current.get("precipMM", 0.0))

        max_c = float(weather.get("maxtempC", temp_c))
        min_c = float(weather.get("mintempC", temp_c))

        report = WeatherReport(
            location=city_name,
            country=country,
            temperature_c=temp_c,
            feels_like_c=feels_c,
            condition=desc,
            humidity_percent=humidity,
            wind_speed_kmh=wind_kmh,
            precipitation_mm=precip,
            daily_max_c=max_c,
            daily_min_c=min_c,
            source="wttr.in",
        )

        return {
            "summary": report.to_summary(),
            "location": report.location,
            "country": report.country,
            "temperature_c": report.temperature_c,
            "feels_like_c": report.feels_like_c,
            "condition": report.condition,
            "humidity_percent": report.humidity_percent,
            "wind_speed_kmh": report.wind_speed_kmh,
            "daily_max_c": report.daily_max_c,
            "daily_min_c": report.daily_min_c,
        }

    def _fetch_open_meteo(self, location: str) -> Dict[str, Any]:
        """Geocode and fetch forecast from Open-Meteo."""
        # Geocode city to lat/lon
        geo_url = (
            f"https://geocoding-api.open-meteo.com/v1/search?"
            f"name={urllib.parse.quote(location)}&count=1&language=en&format=json"
        )
        geo_req = urllib.request.Request(geo_url, headers={"User-Agent": "JARVIS-Assistant/1.0"})
        with urllib.request.urlopen(geo_req, timeout=self.timeout_seconds) as resp:
            geo_data = json.loads(resp.read().decode("utf-8"))

        results = geo_data.get("results", [])
        if not results:
            raise ValueError(f"Location '{location}' not found in Open-Meteo geocoding database.")

        geo = results[0]
        lat = geo["latitude"]
        lon = geo["longitude"]
        city_name = geo.get("name", location)
        country = geo.get("country", "")

        # Fetch forecast
        w_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&"
            f"current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&"
            f"daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto"
        )
        w_req = urllib.request.Request(w_url, headers={"User-Agent": "JARVIS-Assistant/1.0"})
        with urllib.request.urlopen(w_req, timeout=self.timeout_seconds) as resp:
            w_data = json.loads(resp.read().decode("utf-8"))

        current = w_data["current"]
        daily = w_data.get("daily", {})

        code = int(current.get("weather_code", 0))
        condition = WMO_WEATHER_CODES.get(code, "Clear sky")

        temp_c = float(current.get("temperature_2m", 0.0))
        feels_c = float(current.get("apparent_temperature", temp_c))
        humidity = int(current.get("relative_humidity_2m", 0))
        wind_kmh = float(current.get("wind_speed_10m", 0.0))
        precip = float(current.get("precipitation", 0.0))

        max_c = float(daily.get("temperature_2m_max", [temp_c])[0])
        min_c = float(daily.get("temperature_2m_min", [temp_c])[0])

        report = WeatherReport(
            location=city_name,
            country=country,
            temperature_c=temp_c,
            feels_like_c=feels_c,
            condition=condition,
            humidity_percent=humidity,
            wind_speed_kmh=wind_kmh,
            precipitation_mm=precip,
            daily_max_c=max_c,
            daily_min_c=min_c,
            source="open-meteo",
        )

        return {
            "summary": report.to_summary(),
            "location": report.location,
            "country": report.country,
            "temperature_c": report.temperature_c,
            "feels_like_c": report.feels_like_c,
            "condition": report.condition,
            "humidity_percent": report.humidity_percent,
            "wind_speed_kmh": report.wind_speed_kmh,
            "daily_max_c": report.daily_max_c,
            "daily_min_c": report.daily_min_c,
        }
