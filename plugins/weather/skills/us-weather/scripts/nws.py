#!/usr/bin/env python3
"""US weather from the National Weather Service API (api.weather.gov). Standard library only.

    python3 nws.py LAT,LON [--date DAY | --hours N] [--days N] [--units us|si] [--json]
    python3 nws.py --address "1600 Pennsylvania Ave NW, Washington, DC 20500" [...]

Reports, in the location's own time zone:
  default      the location, active alerts, current conditions, and the forecast
               periods for the next --days days (default 7)
  --hours N    adds the next N hours from the hourly forecast (it runs about 6 days)
  --date DAY   one day instead of current conditions and the multi-day forecast -
               its forecast periods, every hour, and a summary with precipitation,
               snow and ice totals and the strongest gust. DAY is YYYY-MM-DD, today,
               tomorrow, or a weekday name (the next one, today included)

Coordinates are rounded to 4 decimal places, the most the API accepts. --address
geocodes a US street address with the Census Bureau geocoder, which does not
match a city name or a ZIP code on its own.

The API requires a User-Agent that identifies the caller. Set NWS_USER_AGENT to
replace the default, e.g. "(my-weather-app, me@example.com)".

Exit codes: 0 report produced, 2 bad input or no NWS data for that place or day,
3 a service failed after retries.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python 3.8 and earlier
    ZoneInfo = None

API = "https://api.weather.gov"
GEOCODER = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
DEFAULT_USER_AGENT = "(tteschon-skills us-weather, https://github.com/tteschon/skills)"
RETRIES = 3
STALE_OBSERVATION = timedelta(hours=2)
MAX_STATIONS = 3
SEVERITY_ORDER = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3}
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
# Grid layers totalled over a day in --date mode: (API key, report key).
DAY_TOTALS = (("quantitativePrecipitation", "precipitation"),
              ("snowfallAmount", "snow"),
              ("iceAccumulation", "ice"))


class Failure(Exception):
    """A message for the user, and the exit code that goes with it."""

    def __init__(self, message: str, code: int = 3):
        super().__init__(message)
        self.code = code


class NotFound(Failure):
    def __init__(self, message: str):
        super().__init__(message, 2)


# ---------------------------------------------------------------- fetching

def _problem_detail(err: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(err.read().decode("utf-8", "replace"))
        return body.get("detail") or body.get("title") or err.reason
    except (ValueError, OSError, AttributeError):
        return str(err.reason)


def fetch(url: str, params: dict | None = None, accept: str = "application/geo+json") -> dict:
    """GET a JSON document, retrying throttling, server errors and dropped connections."""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    headers = {"User-Agent": os.environ.get("NWS_USER_AGENT") or DEFAULT_USER_AGENT,
               "Accept": accept}
    problem = ""
    for attempt in range(RETRIES + 1):
        if attempt:
            time.sleep(2 ** (attempt - 1))
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as err:
            problem = f"HTTP {err.code}: {_problem_detail(err)}"
            if err.code == 404:
                raise NotFound(problem) from None
            if err.code == 403:
                raise Failure(f"{url} refused the request ({problem}). The API blocks "
                              "requests without an identifying User-Agent - set "
                              "NWS_USER_AGENT - and a network proxy can also refuse the host.") from None
            if err.code != 429 and err.code < 500:
                raise Failure(f"{url} - {problem}") from None
        except (urllib.error.URLError, OSError, ValueError) as err:
            problem = str(getattr(err, "reason", err))
    raise Failure(f"{url} failed after {RETRIES + 1} attempts - {problem}")


def coordinate(value: float) -> str:
    """At most 4 decimals - the API answers a longer coordinate with a redirect."""
    text = f"{round(value, 4):.4f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def parse_coordinates(parts: list[str]) -> tuple[float, float]:
    text = " ".join(parts).strip()
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)", text)
    if not match:
        raise Failure(f"Expected LAT,LON in decimal degrees, e.g. 39.7456,-97.0892 - got {text!r}", 2)
    lat, lon = float(match.group(1)), float(match.group(2))
    if not -90 <= lat <= 90:
        raise Failure(f"Latitude {lat} is out of range. Pass LAT,LON with latitude first.", 2)
    if not -180 <= lon <= 180:
        raise Failure(f"Longitude {lon} is out of range.", 2)
    return round(lat, 4), round(lon, 4)


def geocode(address: str) -> tuple[float, float, str]:
    data = fetch(GEOCODER, {"address": address, "benchmark": "Public_AR_Current",
                            "format": "json"}, accept="application/json")
    matches = (data.get("result") or {}).get("addressMatches") or []
    if not matches:
        raise Failure(f"The Census geocoder found no match for {address!r}. It matches US "
                      "street addresses only - for a city, town or ZIP code, pass its "
                      "approximate coordinates instead.", 2)
    best = matches[0]
    return round(best["coordinates"]["y"], 4), round(best["coordinates"]["x"], 4), best["matchedAddress"]


def lookup_point(lat: float, lon: float) -> dict:
    try:
        return fetch(f"{API}/points/{coordinate(lat)},{coordinate(lon)}")
    except NotFound:
        hint = ""
        if lon > 0 and not 130 <= lon <= 180:
            hint = f" Longitudes west of Greenwich are negative - did you mean {lat},{-lon}?"
        raise Failure(f"NWS has no data for {coordinate(lat)},{coordinate(lon)}. It covers the "
                      f"United States and its territories only.{hint}", 2) from None


# ---------------------------------------------------------------- units and times

def convert(value: float | None, unit_code: str | None, units: str) -> dict | None:
    """An API quantity in the report's units, as {"value", "unit"}; None when missing."""
    if value is None:
        return None
    code = (unit_code or "").split(":")[-1]
    us = units == "us"
    if code == "degC":
        number, unit, digits = (value * 9 / 5 + 32, "°F", 0) if us else (value, "°C", 0)
    elif code == "degF":
        number, unit, digits = (value, "°F", 0) if us else ((value - 32) * 5 / 9, "°C", 0)
    elif code == "km_h-1":
        number, unit, digits = (value / 1.609344, "mph", 0) if us else (value, "km/h", 0)
    elif code == "m_s-1":
        number, unit, digits = (value * 2.236936, "mph", 0) if us else (value * 3.6, "km/h", 0)
    elif code == "Pa":
        number, unit, digits = (value / 3386.389, "inHg", 2) if us else (value / 100, "hPa", 0)
    elif code == "mm":
        number, unit, digits = (value / 25.4, "in", 2) if us else (value, "mm", 1)
    elif code == "m":
        number, unit, digits = (value / 1609.344, "mi", 1) if us else (value / 1000, "km", 1)
    elif code == "percent":
        number, unit, digits = value, "%", 0
    else:
        number, unit, digits = value, code, 1
    number = round(number, digits)
    return {"value": int(number) if digits == 0 else number, "unit": unit}


def quantity(field: dict | None, units: str) -> dict | None:
    field = field or {}
    return convert(field.get("value"), field.get("unitCode"), units)


def compass(degrees: float | None) -> str | None:
    if degrees is None:
        return None
    return COMPASS[int((degrees % 360) / 22.5 + 0.5) % 16]


def parse_time(text: str | None) -> datetime | None:
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def location_tz(name: str | None, sample: str | None):
    """The location's zone; a fixed offset from a forecast timestamp if zoneinfo cannot load it."""
    if name and ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:  # missing tzdata, e.g. Windows without the tzdata package
            pass
    sample_time = parse_time(sample)
    return sample_time.tzinfo if sample_time and sample_time.tzinfo else timezone.utc


def local(text: str | None, tz) -> datetime | None:
    moment = parse_time(text)
    return moment.astimezone(tz) if moment else None


def clock(text: str | None, tz, with_day: bool = True) -> str:
    moment = local(text, tz)
    if not moment:
        return "?"
    return moment.strftime("%a %H:%M" if with_day else "%H:%M")


def interval(valid_time: str) -> tuple[datetime, datetime]:
    """'2026-11-26T00:00:00+00:00/PT6H' -> (start, end)."""
    start_text, _, duration = valid_time.partition("/")
    start = parse_time(start_text)
    match = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?", duration)
    if not match:
        raise ValueError(f"Unrecognised duration in {valid_time!r}")
    days, hours, minutes = (int(group or 0) for group in match.groups())
    return start, start + timedelta(days=days, hours=hours, minutes=minutes)


def top_number(text: str | None) -> int | None:
    """'5 to 10 mph' -> 10."""
    numbers = [int(n) for n in re.findall(r"\d+", text or "")]
    return max(numbers) if numbers else None


# ---------------------------------------------------------------- sections

def describe_location(points: dict, lat: float, lon: float, units: str) -> dict:
    props = points["properties"]
    near = ((props.get("relativeLocation") or {}).get("properties")) or {}
    astro = props.get("astronomicalData") or {}
    zone = props.get("forecastZone") or ""
    return {
        "latitude": lat,
        "longitude": lon,
        "near": {
            "city": near.get("city"),
            "state": near.get("state"),
            "distance": quantity(near.get("distance"), units),
            "direction": compass((near.get("bearing") or {}).get("value")),
        },
        "office": props.get("cwa") or props.get("gridId"),
        "time_zone": props.get("timeZone"),
        "forecast_zone": zone.rsplit("/", 1)[-1] or None,
        "sunrise": astro.get("sunrise"),
        "sunset": astro.get("sunset"),
    }


def describe_alerts(alerts: dict) -> tuple[list[dict], int]:
    """Alerts in effect, most severe first, and how many were left out as over.

    /alerts/active keeps returning a watch that was upgraded to a warning, or an
    advisory that was cancelled, until its end time. Those carry urgency Past or
    response AllClear, and reporting them beside their replacement misleads.
    """
    items, over = [], 0
    for feature in alerts.get("features") or []:
        p = feature.get("properties") or {}
        if (p.get("messageType") == "Cancel" or p.get("urgency") == "Past"
                or p.get("response") == "AllClear"):
            over += 1
            continue
        nws_headline = ((p.get("parameters") or {}).get("NWSheadline") or [None])[0]
        items.append({
            "event": p.get("event"),
            "severity": p.get("severity"),
            "urgency": p.get("urgency"),
            "certainty": p.get("certainty"),
            "headline": nws_headline or p.get("headline"),
            "sender": p.get("senderName"),
            "area": p.get("areaDesc"),
            "issued": p.get("sent"),
            "onset": p.get("onset") or p.get("effective"),
            "ends": p.get("ends"),
            "expires": p.get("expires"),
            "description": p.get("description"),
            "instruction": p.get("instruction"),
        })
    items.sort(key=lambda a: (SEVERITY_ORDER.get(a["severity"], 9), a["onset"] or ""))
    return items, over


def from_metar(raw: str | None) -> dict:
    """Temperature, dewpoint, wind and pressure read from a raw METAR, in API units.

    The API often leaves decoded fields null (quality control "Z") while the
    METAR it received has them - hour after hour at PHNL and TJSJ, for example.
    """
    found: dict = {}
    if not raw:
        return found
    tenths = re.search(r"\bT([01])(\d{3})([01])(\d{3})\b", raw)
    whole = re.search(r"(?<![\dA-Z/])(M?\d{2})/(M?\d{2})?(?=\s|$)", raw)
    if tenths:
        found["temperature"] = (-1 if tenths.group(1) == "1" else 1) * int(tenths.group(2)) / 10
        found["dewpoint"] = (-1 if tenths.group(3) == "1" else 1) * int(tenths.group(4)) / 10
    elif whole:
        found["temperature"] = int(whole.group(1).replace("M", "-"))
        if whole.group(2):
            found["dewpoint"] = int(whole.group(2).replace("M", "-"))
    wind = re.search(r"\b(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?KT\b", raw)
    if wind:
        found["windDirection"] = None if wind.group(1) == "VRB" else int(wind.group(1))
        found["windSpeed"] = int(wind.group(2)) * 1.852
        found["windGust"] = int(wind.group(3)) * 1.852 if wind.group(3) else None
    altimeter = re.search(r"\bA(\d{4})\b", raw)
    if altimeter:
        found["barometricPressure"] = int(altimeter.group(1)) / 100 * 3386.389
    if "temperature" in found and "dewpoint" in found:
        t, d = found["temperature"], found["dewpoint"]
        found["relativeHumidity"] = 100 * math.exp(17.625 * d / (243.04 + d)) / math.exp(17.625 * t / (243.04 + t))
    return found


METAR_UNITS = {"temperature": "wmoUnit:degC", "dewpoint": "wmoUnit:degC",
               "windDirection": "wmoUnit:degree_(angle)", "windSpeed": "wmoUnit:km_h-1",
               "windGust": "wmoUnit:km_h-1", "barometricPressure": "wmoUnit:Pa",
               "relativeHumidity": "wmoUnit:percent"}


def describe_observation(obs: dict, station: dict, units: str, now: datetime) -> dict:
    p = dict(obs.get("properties") or {})
    s = station.get("properties") or {}
    observed = parse_time(p.get("timestamp"))
    filled = []
    if (p.get("temperature") or {}).get("value") is None:
        for key, value in from_metar(p.get("rawMessage")).items():
            if (p.get(key) or {}).get("value") is None and value is not None:
                p[key] = {"value": value, "unitCode": METAR_UNITS[key]}
                filled.append(key)
    return {
        "station": {"id": s.get("stationIdentifier"), "name": s.get("name"),
                    "distance": quantity(s.get("distance"), units)},
        "observed": p.get("timestamp"),
        "age_minutes": round((now - observed).total_seconds() / 60) if observed else None,
        "description": p.get("textDescription") or None,
        "temperature": quantity(p.get("temperature"), units),
        "wind_chill": quantity(p.get("windChill"), units),
        "heat_index": quantity(p.get("heatIndex"), units),
        "dewpoint": quantity(p.get("dewpoint"), units),
        "humidity": quantity(p.get("relativeHumidity"), units),
        "wind_direction": compass((p.get("windDirection") or {}).get("value")),
        "wind_speed": quantity(p.get("windSpeed"), units),
        "wind_gust": quantity(p.get("windGust"), units),
        "pressure": quantity(p.get("barometricPressure"), units),
        "visibility": quantity(p.get("visibility"), units),
        "precipitation_last_hour": quantity(p.get("precipitationLastHour"), units),
        "read_from_raw_metar": filled,
    }


def current_conditions(stations: dict, units: str, now: datetime) -> tuple[dict | None, list[str]]:
    """The nearest fresh observation with a temperature, trying up to MAX_STATIONS stations."""
    notes, fallback = [], None
    features = sorted(stations.get("features") or [],
                      key=lambda f: ((f.get("properties") or {}).get("distance") or {}).get("value") or 0)
    for feature in features[:MAX_STATIONS]:
        sid = (feature.get("properties") or {}).get("stationIdentifier")
        try:
            obs = fetch(f"{API}/stations/{sid}/observations/latest")
        except Failure as err:
            notes.append(f"Station {sid}: {err}")
            continue
        conditions = describe_observation(obs, feature, units, now)
        if conditions["temperature"] is None:
            continue
        if conditions["age_minutes"] is not None and conditions["age_minutes"] <= STALE_OBSERVATION.total_seconds() / 60:
            return conditions, notes
        fallback = fallback or conditions
    if fallback:
        notes.append(f"No station within the nearest {MAX_STATIONS} reported in the last "
                     f"{int(STALE_OBSERVATION.total_seconds() // 3600)} hours - showing an older observation.")
    return fallback, notes


def describe_period(p: dict) -> dict:
    return {
        "name": p.get("name"),
        "start": p.get("startTime"),
        "end": p.get("endTime"),
        "is_daytime": p.get("isDaytime"),
        "temperature": {"value": p.get("temperature"), "unit": "°" + (p.get("temperatureUnit") or "")},
        "precip_chance": (p.get("probabilityOfPrecipitation") or {}).get("value"),
        "wind": " ".join(x for x in (p.get("windDirection"), p.get("windSpeed")) if x),
        "short": p.get("shortForecast"),
        "detail": p.get("detailedForecast"),
    }


def describe_hour(p: dict, units: str) -> dict:
    return {
        "start": p.get("startTime"),
        "temperature": {"value": p.get("temperature"), "unit": "°" + (p.get("temperatureUnit") or "")},
        "precip_chance": (p.get("probabilityOfPrecipitation") or {}).get("value"),
        "humidity": (p.get("relativeHumidity") or {}).get("value"),
        # Always degC in the API, even when the rest of the hour is in US units.
        "dewpoint": quantity(p.get("dewpoint"), units),
        "wind": " ".join(x for x in (p.get("windDirection"), p.get("windSpeed")) if x),
        "short": p.get("shortForecast"),
    }


def grid_day(grid: dict, start: datetime, end: datetime, units: str) -> dict:
    """Totals and the strongest gust over [start, end) from the raw forecast grid.

    Grid values cover intervals (often 6 hours) that need not line up with local
    midnight, so an amount is shared out by how much of its interval falls inside
    the day. Each total also says how far into the day the grid reached.
    """
    props = grid.get("properties") or {}
    summary = {}
    for key, name in DAY_TOTALS:
        layer = props.get(key) or {}
        total, reached = 0.0, None
        for item in layer.get("values") or []:
            if item.get("value") is None:
                continue
            a, b = interval(item["validTime"])
            overlap = (min(b, end) - max(a, start)).total_seconds()
            if overlap <= 0:
                continue
            total += item["value"] * overlap / (b - a).total_seconds()
            reached = max(reached, min(b, end)) if reached else min(b, end)
        if reached is None:
            summary[name] = None
            continue
        summary[name] = convert(total, layer.get("uom"), units)
        if reached < end:
            summary[name]["through"] = reached.isoformat()
    layer = props.get("windGust") or {}
    gusts = []
    for item in layer.get("values") or []:
        a, b = interval(item["validTime"])
        if item.get("value") is not None and a < end and b > start:
            gusts.append((item["value"], max(a, start)))
    if gusts:
        value, when = max(gusts, key=lambda g: g[0])
        summary["max_gust"] = dict(convert(value, layer.get("uom"), units), at=when.isoformat())
    else:
        summary["max_gust"] = None
    return summary


def summarise_hours(hours: list[dict]) -> dict | None:
    if not hours:
        return None
    temps = [h["temperature"]["value"] for h in hours if h["temperature"]["value"] is not None]
    chances = [(h["precip_chance"] or 0, h["start"]) for h in hours]
    peak, peak_at = max(chances, key=lambda c: c[0])
    winds = [(top_number(h["wind"]), h["start"]) for h in hours if top_number(h["wind"]) is not None]
    wind_peak, wind_at = max(winds, key=lambda w: w[0]) if winds else (None, None)
    wind_unit = re.search(r"mph|km/h", " ".join(h["wind"] or "" for h in hours))
    humidity = [h["humidity"] for h in hours if h["humidity"] is not None]
    unit = hours[0]["temperature"]["unit"]
    return {
        "hours": len(hours),
        "from": hours[0]["start"],
        "to": hours[-1]["start"],
        "temperature_low": {"value": min(temps), "unit": unit} if temps else None,
        "temperature_high": {"value": max(temps), "unit": unit} if temps else None,
        "precip_chance_peak": peak,
        "precip_chance_peak_at": peak_at,
        "wind_peak": ({"value": wind_peak, "unit": wind_unit.group(0) if wind_unit else "", "at": wind_at}
                      if winds else None),
        "humidity_range": [min(humidity), max(humidity)] if humidity else None,
    }


def resolve_day(text: str, today: date) -> date:
    t = text.strip().lower()
    if t == "today":
        return today
    if t == "tomorrow":
        return today + timedelta(days=1)
    if len(t) >= 3:
        for index, name in enumerate(WEEKDAYS):
            if name.startswith(t):
                return today + timedelta(days=(index - today.weekday()) % 7)
    try:
        return date.fromisoformat(t)
    except ValueError:
        raise Failure(f"--date takes YYYY-MM-DD, today, tomorrow or a weekday name - got {text!r}", 2) from None


# ---------------------------------------------------------------- the report

def build_report(lat: float, lon: float, *, units: str = "us", days: int = 7,
                 hours: int | None = None, day: str | None = None,
                 address: str | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    points = lookup_point(lat, lon)
    props = points["properties"]
    report = {"location": describe_location(points, lat, lon, units), "units": units,
              "generated": now.isoformat(timespec="seconds"), "notes": []}
    if address:
        report["location"]["address"] = address

    try:
        alerts = fetch(f"{API}/alerts/active", {"point": f"{coordinate(lat)},{coordinate(lon)}",
                                                "status": "actual"})
        items, over = describe_alerts(alerts)
        report["alerts"] = {"checked": True, "items": items, "left_out_as_over": over}
    except Failure as err:
        report["alerts"] = {"checked": False, "error": str(err), "items": [], "left_out_as_over": 0}

    if not props.get("forecast"):
        # Offshore waters and some territories (American Samoa) have no forecast
        # grid. Land zones still have a text forecast; marine zones are not served.
        zone = report["location"]["forecast_zone"]
        try:
            text = fetch(f"{API}/zones/forecast/{zone}/forecast")["properties"]
            report["zone_forecast"] = {
                "zone": zone, "updated": text.get("updated"),
                "periods": [{"name": p.get("name"), "detail": p.get("detailedForecast")}
                            for p in (text.get("periods") or [])[: max(days, 1) * 2]]}
            report["notes"].append(f"NWS has no point forecast here, only the text forecast for zone "
                                   f"{zone} - no current conditions, hourly figures or day totals.")
        except NotFound:
            report["notes"].append(f"NWS has no point forecast here: it is in marine zone {zone}, and "
                                   "the API serves no marine forecasts. See https://www.weather.gov/marine.")
        return report

    unit_params = {"units": "si"} if units == "si" else None
    forecast = fetch(props["forecast"], unit_params)
    periods = [describe_period(p) for p in forecast["properties"].get("periods") or []]
    tz = location_tz(props.get("timeZone"), periods[0]["start"] if periods else None)
    report["forecast_updated"] = forecast["properties"].get("updateTime")

    if day is None:
        if props.get("observationStations"):
            try:
                stations = fetch(props["observationStations"])
                report["now"], notes = current_conditions(stations, units, now)
                report["notes"].extend(notes)
            except Failure as err:
                report["now"] = None
                report["notes"].append(f"Current conditions unavailable - {err}")
        report["forecast"] = periods[: max(days, 1) * 2]
        if hours:
            hourly = fetch(props["forecastHourly"], unit_params)
            report["hourly"] = [describe_hour(p, units) for p in hourly["properties"]["periods"][:hours]]
        return report

    target = resolve_day(day, now.astimezone(tz).date())
    if target < now.astimezone(tz).date():
        raise Failure(f"{target} has passed. The API has no past forecasts; recent observations "
                      "go back about a week at /stations/<id>/observations.", 2)
    day_periods = [p for p in periods if local(p["start"], tz).date() == target]
    hourly = fetch(props["forecastHourly"], unit_params)
    day_hours = [describe_hour(p, units) for p in hourly["properties"]["periods"]
                 if local(p["startTime"], tz).date() == target]
    if not day_periods and not day_hours:
        last = periods[-1]["end"] if periods else None
        raise Failure(f"{target} is beyond the NWS forecast, which runs to {clock(last, tz)} "
                      f"({local(last, tz).date() if last else '?'}).", 2)
    start = datetime(target.year, target.month, target.day, tzinfo=tz)
    end = datetime.combine(target + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    # For today, count from the current hour - the hourly rows start there too.
    start = max(start, now.astimezone(tz).replace(minute=0, second=0, microsecond=0))
    report["day"] = {"date": target.isoformat(), "periods": day_periods, "hours": day_hours,
                     "summary": summarise_hours(day_hours)}
    try:
        grid = fetch(props["forecastGridData"])
        report["day"]["totals"] = grid_day(grid, start, end, units)
    except Failure as err:
        report["day"]["totals"] = None
        report["notes"].append(f"Precipitation totals unavailable - {err}")
    return report


# ---------------------------------------------------------------- text output

def fmt(q: dict | None) -> str:
    if not q or q.get("value") is None:
        return "?"
    unit = q["unit"]
    return f"{q['value']}{unit}" if unit.startswith("°") or unit == "%" else f"{q['value']} {unit}"


def paragraphs(text: str | None, indent: str) -> list[str]:
    out = []
    for block in re.split(r"\n\s*\n", text or ""):
        block = " ".join(block.split())
        if block:
            out.append(indent + block)
    return out


def render(report: dict) -> str:
    loc = report["location"]
    tz = location_tz(loc["time_zone"], report.get("forecast_updated"))
    lines = []
    near = loc["near"]
    where = f"{coordinate(loc['latitude'])}, {coordinate(loc['longitude'])}"
    if near.get("city"):
        if near["distance"] and near["distance"]["value"] < 1:
            where += f" - in {near['city']}, {near['state']}"
        else:
            where += f" - {fmt(near['distance'])} {near['direction'] or ''} of {near['city']}, {near['state']}"
    lines.append(f"LOCATION  {where}")
    if loc.get("address"):
        lines.append(f"          geocoded from {loc['address']}")
    detail = f"NWS office {loc['office']}, time zone {loc['time_zone']}"
    if loc.get("sunrise") and loc.get("sunset"):
        detail += f", sunrise {clock(loc['sunrise'], tz, False)}, sunset {clock(loc['sunset'], tz, False)}"
    lines.append(f"          {detail}")

    alerts = report["alerts"]
    lines.append("")
    if not alerts["checked"]:
        lines.append(f"ALERTS    NOT CHECKED - {alerts['error']}")
    elif not alerts["items"]:
        lines.append("ALERTS    none in effect")
    else:
        lines.append(f"ALERTS    {len(alerts['items'])} in effect")
        for a in alerts["items"]:
            lines.append(f"  {a['event']} - {a['severity']}, {a['urgency']}, {a['certainty']} ({a['sender']})")
            onset = parse_time(a["onset"])
            if onset and onset > parse_time(report["generated"]):
                lines.append(f"    Starts {clock(a['onset'], tz)}")
            if a["ends"]:
                lines.append(f"    Ends {clock(a['ends'], tz)}")
            else:
                lines.append(f"    No end time given - this message expires {clock(a['expires'], tz)} "
                             "and may be extended or replaced")
            if a["headline"]:
                lines.append(f"    {a['headline']}")
            lines.extend(paragraphs(a["description"], "    "))
            if a["instruction"]:
                lines.extend(paragraphs("What to do: " + a["instruction"], "    "))
    if alerts["checked"] and alerts["left_out_as_over"]:
        lines.append(f"          ({alerts['left_out_as_over']} upgraded, cancelled or ended alert(s) left out)")

    now = report.get("now")
    if "now" in report:
        lines.append("")
        if not now:
            lines.append("NOW       no recent observation")
        else:
            st = now["station"]
            age = now["age_minutes"]
            age_text = f"{age} min ago" if age is not None and age < 120 else f"{round((age or 0) / 60)} h ago"
            lines.append(f"NOW       {st['name']} ({st['id']}), {fmt(st['distance'])} away, "
                         f"observed {clock(now['observed'], tz)} ({age_text})")
            parts = [now["description"] or "", f"{fmt(now['temperature'])}"]
            feels = now["wind_chill"] or now["heat_index"]
            if feels and feels["value"] != (now["temperature"] or {}).get("value"):
                parts.append(f"feels like {fmt(feels)}")
            if now["wind_speed"] and now["wind_speed"]["value"] == 0:
                parts.append("calm")
            elif now["wind_speed"]:
                wind = f"wind {now['wind_direction'] or ''} {fmt(now['wind_speed'])}".replace("  ", " ")
                if now["wind_gust"]:
                    wind += f" gusting {fmt(now['wind_gust'])}"
                parts.append(wind)
            if now["humidity"]:
                parts.append(f"humidity {fmt(now['humidity'])}")
            if now["dewpoint"]:
                parts.append(f"dewpoint {fmt(now['dewpoint'])}")
            if now["pressure"]:
                parts.append(f"pressure {fmt(now['pressure'])}")
            if now["visibility"]:
                parts.append(f"visibility {fmt(now['visibility'])}")
            if now["precipitation_last_hour"]:
                parts.append(f"precipitation last hour {fmt(now['precipitation_last_hour'])}")
            lines.append("          " + ", ".join(p for p in parts if p))
            if now.get("read_from_raw_metar"):
                fields = ", ".join(re.sub(r"([A-Z])", r" \1", f).lower() for f in now["read_from_raw_metar"])
                lines.append(f"          ({fields} read from the station's raw METAR - the API left them blank)")

    def period_lines(periods):
        for p in periods:
            temp = ("High " if p["is_daytime"] else "Low ") + fmt(p["temperature"])
            chance = "-" if p["precip_chance"] is None else f"{p['precip_chance']}%"
            lines.append(f"  {p['name']:<20} {temp:<10} precip {chance:<4} "
                         f"wind {p['wind']:<18} {p['short']}")
            lines.extend(paragraphs(p["detail"], "      "))

    def hour_lines(hours):
        lines.append(f"  {'hour':<10} {'temp':>5} {'precip':>6} {'humid':>5} {'dewpt':>6}  {'wind':<14} sky")
        for h in hours:
            chance = "-" if h["precip_chance"] is None else f"{h['precip_chance']}%"
            humid = "-" if h["humidity"] is None else f"{h['humidity']}%"
            lines.append(f"  {clock(h['start'], tz):<10} {fmt(h['temperature']):>5} {chance:>6} {humid:>5} "
                         f"{fmt(h['dewpoint']):>6}  {h['wind']:<14} {h['short']}")

    if report.get("forecast"):
        lines.append("")
        lines.append(f"FORECAST  issued {clock(report.get('forecast_updated'), tz)}")
        period_lines(report["forecast"])
    if report.get("zone_forecast"):
        zone = report["zone_forecast"]
        lines.append("")
        lines.append(f"FORECAST  zone {zone['zone']} text forecast, issued {clock(zone['updated'], tz)}")
        for p in zone["periods"]:
            lines.append(f"  {p['name']}")
            lines.extend(paragraphs(p["detail"], "      "))
    if report.get("hourly"):
        lines.append("")
        lines.append(f"HOURLY    next {len(report['hourly'])} hours")
        hour_lines(report["hourly"])

    day = report.get("day")
    if day:
        lines.append("")
        lines.append(f"DAY       {date.fromisoformat(day['date']).strftime('%A')} "
                     f"{day['date']}, forecast issued {clock(report.get('forecast_updated'), tz)}")
        s, t = day["summary"], day.get("totals")
        if s:
            span = f"{clock(s['from'], tz, False)}-{clock(s['to'], tz, False)}"
            lines.append(f"  Hours     {s['hours']} hourly forecasts, {span}")
            lines.append(f"  Temp      {fmt(s['temperature_low'])} to {fmt(s['temperature_high'])}")
            if s["precip_chance_peak"]:
                lines.append(f"  Precip    chance peaks at {s['precip_chance_peak']}% at "
                             f"{clock(s['precip_chance_peak_at'], tz, False)}")
            else:
                lines.append("  Precip    0% chance in every hour")
            if s["wind_peak"]:
                lines.append(f"  Wind      up to {s['wind_peak']['value']} {s['wind_peak']['unit']} "
                             f"at {clock(s['wind_peak']['at'], tz, False)} (sustained)")
            if s["humidity_range"]:
                lines.append(f"  Humidity  {s['humidity_range'][0]}% to {s['humidity_range'][1]}%")
        else:
            lines.append("  No hourly forecast reaches this day - only the periods below.")
        if t:
            for key, label in (("precipitation", "Amount   "), ("snow", "Snow     "), ("ice", "Ice      ")):
                q = t.get(key)
                if q is None:
                    continue
                through = f" (grid only reaches {clock(q['through'], tz)})" if q.get("through") else ""
                what = " liquid equivalent, rain and melted snow" if key == "precipitation" else ""
                lines.append(f"  {label} {fmt(q)}{what}{through}")
            if t.get("max_gust"):
                lines.append(f"  Gusts     up to {fmt(t['max_gust'])} around {clock(t['max_gust']['at'], tz, False)}")
        if day["periods"]:
            lines.append("")
            period_lines(day["periods"])
        if day["hours"]:
            lines.append("")
            hour_lines(day["hours"])

    if report["notes"]:
        lines.append("")
        lines.extend(f"NOTE      {n}" for n in report["notes"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="\n\n".join(__doc__.split("\n\n")[1:]))
    parser.add_argument("coordinates", nargs="*", metavar="LAT,LON",
                        help="decimal degrees, latitude first, e.g. 39.7456,-97.0892")
    parser.add_argument("--address", help="a US street address, geocoded by the Census Bureau")
    when = parser.add_mutually_exclusive_group()
    when.add_argument("--date", metavar="DAY", help="YYYY-MM-DD, today, tomorrow or a weekday")
    when.add_argument("--hours", type=int, metavar="N", help="add the next N hourly forecasts")
    parser.add_argument("--days", type=int, default=7, help="days of forecast periods (default 7)")
    parser.add_argument("--units", choices=("us", "si"), default="us")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    argv = sys.argv[1:] if argv is None else list(argv)
    # argparse reads "-14.2756,-170.702" as an unknown option, so take coordinate
    # pairs out first. A bare negative number such as -97.0892 already parses.
    pairs = [a for a in argv if re.fullmatch(r"-\d+(?:\.\d+)?,-?\d+(?:\.\d+)?", a)]
    args = parser.parse_args([a for a in argv if a not in pairs])
    args.coordinates = pairs + args.coordinates

    try:
        if bool(args.coordinates) == bool(args.address):
            raise Failure("Give either LAT,LON or --address, not both and not neither.", 2)
        if args.address:
            lat, lon, matched = geocode(args.address)
        else:
            (lat, lon), matched = parse_coordinates(args.coordinates), None
        report = build_report(lat, lon, units=args.units, days=args.days, hours=args.hours,
                              day=args.date, address=matched)
    except Failure as err:
        print(f"error: {err}", file=sys.stderr)
        return err.code
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
