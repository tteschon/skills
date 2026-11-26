"""Checks us-weather's nws.py against responses recorded from api.weather.gov.

    python3 plugins/weather/tests/test_nws.py

Offline: fetch is replaced by a router over tests/fixtures, which hold real
responses for 39.7456,-97.0892 (near Linn, KS) and a Washington, DC alert set,
recorded at 2026-11-26T03:11Z - Wednesday 21:11 in America/Chicago.
"""

import copy
import importlib.util
import io
import json
import unittest
import urllib.error
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
SCRIPT = HERE.parent / "skills/us-weather/scripts/nws.py"
spec = importlib.util.spec_from_file_location("nws", SCRIPT)
nws = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nws)

NOW = datetime(2026, 11, 26, 3, 15, tzinfo=timezone.utc)
LAT, LON = 39.7456, -97.0892
GRID = "https://api.weather.gov/gridpoints/TOP/32,81"


def fixture(name):
    return json.loads((HERE / "fixtures" / name).read_text())


class Router:
    """Stands in for nws.fetch: URL -> fixture name, a dict, or an exception to raise."""

    def __init__(self, **overrides):
        self.routes = {
            "https://api.weather.gov/points/39.7456,-97.0892": "points_linn.json",
            "https://api.weather.gov/alerts/active": "alerts_none.json",
            f"{GRID}/forecast": "forecast_linn.json",
            f"{GRID}/forecast/hourly": "hourly_linn.json",
            GRID: "grid_linn.json",
            f"{GRID}/stations": "stations_linn.json",
            "https://api.weather.gov/stations/KMYZ/observations/latest": "obs_kmyz.json",
        }
        self.routes.update(overrides)
        self.calls = []

    def __call__(self, url, params=None, accept=None):
        self.calls.append((url, params))
        if url not in self.routes:
            raise nws.NotFound(f"HTTP 404: no fixture for {url}")
        target = self.routes[url]
        if isinstance(target, Exception):
            raise target
        return copy.deepcopy(target) if isinstance(target, dict) else fixture(target)


class WithRouter(unittest.TestCase):
    def route(self, **overrides):
        self.router = Router(**overrides)
        self._real_fetch, nws.fetch = nws.fetch, self.router
        self.addCleanup(setattr, nws, "fetch", self._real_fetch)
        return self.router


class Coordinates(unittest.TestCase):
    def test_rounded_to_four_decimals_without_trailing_zeros(self):
        self.assertEqual(nws.coordinate(39.745612), "39.7456")
        self.assertEqual(nws.coordinate(-97.0), "-97")

    def test_pair_in_one_or_two_arguments(self):
        self.assertEqual(nws.parse_coordinates(["39.7456,-97.0892"]), (LAT, LON))
        self.assertEqual(nws.parse_coordinates(["39.7456", "-97.0892"]), (LAT, LON))

    def test_longitude_first_is_rejected(self):
        with self.assertRaises(nws.Failure) as caught:
            nws.parse_coordinates(["-97.0892,39.7456"])
        self.assertEqual(caught.exception.code, 2)

    def test_southern_and_western_pair_reaches_the_report(self):
        # argparse alone reads "-14.2756,-170.702" as an unknown option.
        seen = {}

        def fake_report(lat, lon, **kwargs):
            seen["at"] = (lat, lon)
            return {}

        real, nws.build_report = nws.build_report, fake_report
        self.addCleanup(setattr, nws, "build_report", real)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(nws.main(["-14.2756,-170.702", "--json"]), 0)
        self.assertEqual(seen["at"], (-14.2756, -170.702))


class Units(unittest.TestCase):
    def test_conversions_to_us_units(self):
        self.assertEqual(nws.convert(0, "wmoUnit:degC", "us"), {"value": 32, "unit": "°F"})
        self.assertEqual(nws.convert(16.09344, "wmoUnit:km_h-1", "us"), {"value": 10, "unit": "mph"})
        self.assertEqual(nws.convert(101591.67, "wmoUnit:Pa", "us"), {"value": 30.0, "unit": "inHg"})
        self.assertEqual(nws.convert(25.4, "wmoUnit:mm", "us"), {"value": 1.0, "unit": "in"})
        self.assertEqual(nws.convert(1609.344, "wmoUnit:m", "us"), {"value": 1.0, "unit": "mi"})

    def test_si_keeps_metric_but_uses_hpa_and_km(self):
        self.assertEqual(nws.convert(101300, "wmoUnit:Pa", "si"), {"value": 1013, "unit": "hPa"})
        self.assertEqual(nws.convert(16090, "wmoUnit:m", "si"), {"value": 16.1, "unit": "km"})

    def test_missing_value_stays_missing(self):
        self.assertIsNone(nws.convert(None, "wmoUnit:degC", "us"))

    def test_hourly_dewpoint_is_celsius_even_in_us_units(self):
        first = fixture("hourly_linn.json")["properties"]["periods"][0]
        self.assertEqual(first["dewpoint"]["unitCode"], "wmoUnit:degC")
        hour = nws.describe_hour(first, "us")
        self.assertEqual(hour["dewpoint"], {"value": 23, "unit": "°F"})  # -5 C
        self.assertEqual(hour["temperature"], {"value": 28, "unit": "°F"})


class Days(unittest.TestCase):
    WEDNESDAY = date(2026, 11, 25)

    def test_words(self):
        self.assertEqual(nws.resolve_day("today", self.WEDNESDAY), self.WEDNESDAY)
        self.assertEqual(nws.resolve_day("tomorrow", self.WEDNESDAY), date(2026, 11, 26))
        self.assertEqual(nws.resolve_day("Saturday", self.WEDNESDAY), date(2026, 11, 28))
        self.assertEqual(nws.resolve_day("sat", self.WEDNESDAY), date(2026, 11, 28))

    def test_weekday_named_today_is_today(self):
        self.assertEqual(nws.resolve_day("wednesday", self.WEDNESDAY), self.WEDNESDAY)
        self.assertEqual(nws.resolve_day("tuesday", self.WEDNESDAY), date(2026, 12, 1))

    def test_bad_day(self):
        for text in ("someday", "we", "2026-13-01"):
            with self.assertRaises(nws.Failure):
                nws.resolve_day(text, self.WEDNESDAY)


class DefaultReport(WithRouter):
    def test_sections(self):
        self.route()
        report = nws.build_report(LAT, LON, now=NOW)
        self.assertEqual(report["location"]["near"]["city"], "Linn")
        self.assertEqual(report["alerts"], {"checked": True, "items": [], "left_out_as_over": 0})
        self.assertEqual(report["now"]["station"]["id"], "KMYZ")
        self.assertEqual(report["now"]["temperature"], {"value": 30, "unit": "°F"})
        self.assertEqual(report["now"]["age_minutes"], 40)
        self.assertEqual(len(report["forecast"]), 14)
        self.assertNotIn("hourly", report)

        text = nws.render(report)
        self.assertIn("4.2 mi N of Linn, KS", text)
        self.assertIn("ALERTS    none in effect", text)
        self.assertIn("Thanksgiving Day", text)

    def test_days_and_hours(self):
        self.route()
        report = nws.build_report(LAT, LON, days=1, hours=6, now=NOW)
        self.assertEqual([p["name"] for p in report["forecast"]], ["Tonight", "Thanksgiving Day"])
        self.assertEqual(len(report["hourly"]), 6)

    def test_si_units_are_requested_from_the_api(self):
        router = self.route()
        nws.build_report(LAT, LON, units="si", now=NOW)
        self.assertIn((f"{GRID}/forecast", {"units": "si"}), router.calls)

    def test_stale_nearest_station_gives_way_to_the_next(self):
        stale = fixture("obs_kmyz.json")
        stale["properties"]["timestamp"] = "2026-11-25T20:35:00+00:00"
        fresh = fixture("obs_kmyz.json")
        fresh["properties"]["temperature"]["value"] = 2.0
        self.route(**{
            "https://api.weather.gov/stations/KMYZ/observations/latest": stale,
            "https://api.weather.gov/stations/KCNK/observations/latest": fresh,
        })
        now = nws.build_report(LAT, LON, now=NOW)["now"]
        self.assertEqual(now["station"]["id"], "KCNK")
        self.assertEqual(now["temperature"]["value"], 36)

    def test_only_stale_observations_are_shown_with_a_note(self):
        stale = fixture("obs_kmyz.json")
        stale["properties"]["timestamp"] = "2026-11-25T20:35:00+00:00"
        self.route(**{"https://api.weather.gov/stations/KMYZ/observations/latest": stale})
        report = nws.build_report(LAT, LON, now=NOW)
        self.assertEqual(report["now"]["age_minutes"], 400)
        self.assertTrue(any("older observation" in n for n in report["notes"]))
        self.assertIn("(7 h ago)", nws.render(report))


class Alerts(WithRouter):
    def test_upgraded_watch_is_left_out_and_warnings_lead(self):
        self.route(**{"https://api.weather.gov/alerts/active": "alerts_dc.json"})
        alerts = nws.build_report(LAT, LON, now=NOW)["alerts"]
        self.assertEqual([a["event"] for a in alerts["items"]], ["Coastal Flood Warning", "Wind Advisory"])
        self.assertEqual(alerts["left_out_as_over"], 1)

    def test_end_time_comes_from_ends_not_expires(self):
        self.route(**{"https://api.weather.gov/alerts/active": "alerts_dc.json"})
        text = nws.render(nws.build_report(LAT, LON, now=NOW))
        # 3 AM Friday Eastern, shown in the location's zone (Central), not expires (05:30 Thu)
        self.assertIn("Ends Fri 02:00", text)
        self.assertIn("Starts Thu 14:00", text)

    def test_no_end_time_says_so(self):
        alerts = fixture("alerts_dc.json")
        alerts["features"][0]["properties"]["ends"] = None
        self.route(**{"https://api.weather.gov/alerts/active": alerts})
        self.assertIn("No end time given", nws.render(nws.build_report(LAT, LON, now=NOW)))

    def test_failed_check_never_reads_as_no_alerts(self):
        self.route(**{"https://api.weather.gov/alerts/active": nws.Failure("HTTP 503: down")})
        text = nws.render(nws.build_report(LAT, LON, now=NOW))
        self.assertIn("ALERTS    NOT CHECKED", text)
        self.assertNotIn("none in effect", text)


class OneDay(WithRouter):
    def test_holiday_period_is_found_by_date_not_name(self):
        self.route()
        day = nws.build_report(LAT, LON, day="thursday", now=NOW)["day"]
        self.assertEqual(day["date"], "2026-11-26")
        self.assertEqual([p["name"] for p in day["periods"]], ["Thanksgiving Day", "Thursday Night"])

    def test_saturday(self):
        self.route()
        report = nws.build_report(LAT, LON, day="saturday", now=NOW)
        day = report["day"]
        self.assertEqual(len(day["hours"]), 24)
        self.assertEqual(day["summary"]["precip_chance_peak"], 77)
        self.assertEqual(day["summary"]["precip_chance_peak_at"], "2026-11-28T18:00:00-06:00")
        self.assertEqual(day["summary"]["temperature_high"], {"value": 51, "unit": "°F"})
        self.assertEqual(day["totals"]["precipitation"]["unit"], "in")
        self.assertNotIn("now", report)
        self.assertIn("DAY       Saturday 2026-11-28", nws.render(report))

    def test_past_and_too_far_ahead(self):
        self.route()
        for when in ("2026-11-24", "2026-12-25"):
            with self.assertRaises(nws.Failure) as caught:
                nws.build_report(LAT, LON, day=when, now=NOW)
            self.assertEqual(caught.exception.code, 2)


class GridTotals(unittest.TestCase):
    tz = nws.location_tz("America/Chicago", None)

    def grid(self, layer, values, uom="wmoUnit:mm"):
        return {"properties": {layer: {"uom": uom, "values": [
            {"validTime": t, "value": v} for t, v in values]}}}

    def day(self, d):
        start = datetime(d.year, d.month, d.day, tzinfo=self.tz)
        return start, datetime(d.year, d.month, d.day + 1, tzinfo=self.tz)

    def test_amount_is_shared_by_overlap(self):
        # 03Z-09Z Saturday is 21:00 Friday to 03:00 Saturday in Chicago: half falls on Saturday.
        grid = self.grid("quantitativePrecipitation", [("2026-11-28T03:00:00+00:00/PT6H", 12.0),
                                                        ("2026-11-28T09:00:00+00:00/P1D", 0.0)])
        totals = nws.grid_day(grid, *self.day(date(2026, 11, 28)), "si")
        self.assertEqual(totals["precipitation"], {"value": 6.0, "unit": "mm"})

    def test_grid_ending_early_says_how_far_it_reached(self):
        grid = self.grid("quantitativePrecipitation", [("2026-11-28T06:00:00+00:00/PT6H", 2.0)])
        totals = nws.grid_day(grid, *self.day(date(2026, 11, 28)), "si")
        self.assertEqual(totals["precipitation"]["through"], "2026-11-28T12:00:00+00:00")

    def test_strongest_gust(self):
        grid = self.grid("windGust", [("2026-11-28T18:00:00+00:00/PT1H", 48.28),
                                      ("2026-11-28T19:00:00+00:00/PT2H", 64.37)], "wmoUnit:km_h-1")
        gust = nws.grid_day(grid, *self.day(date(2026, 11, 28)), "us")["max_gust"]
        self.assertEqual((gust["value"], gust["unit"]), (40, "mph"))

    def test_today_counts_from_the_current_hour(self):
        router = Router()
        router.routes[GRID] = self.grid("windGust", [("2026-11-25T18:00:00+00:00/PT1H", 80.0),
                                                     ("2026-11-26T03:00:00+00:00/PT1H", 16.09)],
                                        "wmoUnit:km_h-1")
        real, nws.fetch = nws.fetch, router
        self.addCleanup(setattr, nws, "fetch", real)
        totals = nws.build_report(LAT, LON, day="today", now=NOW)["day"]["totals"]
        self.assertEqual(totals["max_gust"]["value"], 10)  # noon's 80 km/h gust has passed


class Metar(unittest.TestCase):
    def test_tenths_group_wins(self):
        m = nws.from_metar("PHNL 260153Z 24016G24KT 10SM FEW032 SCT040 SCT050 27/17 A2984 "
                           "RMK AO2 SLP105 T02670172 $")
        self.assertEqual((m["temperature"], m["dewpoint"]), (26.7, 17.2))
        self.assertEqual(m["windDirection"], 240)
        self.assertAlmostEqual(m["windSpeed"], 16 * 1.852)
        self.assertAlmostEqual(m["windGust"], 24 * 1.852)
        self.assertAlmostEqual(m["barometricPressure"], 29.84 * 3386.389)
        self.assertAlmostEqual(m["relativeHumidity"], 56.0, places=0)

    def test_below_freezing_variable_wind_and_runway_range(self):
        m = nws.from_metar("KXYZ 260153Z VRB03KT 1/2SM R04/2000FT FZFG M05/M07 A3012")
        self.assertEqual((m["temperature"], m["dewpoint"]), (-5, -7))
        self.assertIsNone(m["windDirection"])

    def test_blank_api_fields_are_filled_and_flagged(self):
        obs = fixture("obs_kmyz.json")
        for key in ("temperature", "dewpoint", "windSpeed", "relativeHumidity"):
            obs["properties"][key]["value"] = None
        obs["properties"]["rawMessage"] = "KMYZ 260235Z AUTO 04005KT 10SM CLR M01/M07 A3043 RMK AO2"
        station = fixture("stations_linn.json")["features"][0]
        now = nws.describe_observation(obs, station, "us", NOW)
        self.assertEqual(now["temperature"], {"value": 30, "unit": "°F"})
        self.assertIn("temperature", now["read_from_raw_metar"])


class Coverage(WithRouter):
    def test_outside_the_us(self):
        self.route()
        with self.assertRaises(nws.Failure) as caught:
            nws.build_report(51.5074, -0.1278, now=NOW)
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("United States", str(caught.exception))

    def test_east_longitude_hint(self):
        self.route()
        with self.assertRaises(nws.Failure) as caught:
            nws.build_report(39.7456, 97.0892, now=NOW)
        self.assertIn("did you mean 39.7456,-97.0892", str(caught.exception))

    def test_offshore_point_has_no_forecast_but_still_checks_alerts(self):
        router = self.route(**{"https://api.weather.gov/points/38.5,-72": "points_offshore.json"})
        report = nws.build_report(38.5, -72.0, now=NOW)
        self.assertTrue(report["alerts"]["checked"])
        self.assertNotIn("forecast", report)
        self.assertIn("marine zone ANZ920", report["notes"][0])
        self.assertIn(("https://api.weather.gov/zones/forecast/ANZ920/forecast", None), router.calls)


class Fetching(unittest.TestCase):
    def setUp(self):
        self._sleep, nws.time.sleep = nws.time.sleep, lambda s: None
        self._open = nws.urllib.request.urlopen
        self.addCleanup(setattr, nws.time, "sleep", self._sleep)
        self.addCleanup(setattr, nws.urllib.request, "urlopen", self._open)

    def respond(self, *outcomes):
        attempts = []

        def fake_open(request, timeout):
            attempts.append(request)
            outcome = outcomes[len(attempts) - 1]
            if isinstance(outcome, Exception):
                raise outcome
            return io.BytesIO(json.dumps(outcome).encode())

        nws.urllib.request.urlopen = fake_open
        return attempts

    def error(self, code):
        body = io.BytesIO(json.dumps({"detail": f"status {code}"}).encode())
        return urllib.error.HTTPError("https://api.weather.gov/x", code, "err", {}, body)

    def test_server_errors_are_retried(self):
        attempts = self.respond(self.error(500), self.error(503), {"ok": True})
        self.assertEqual(nws.fetch("https://api.weather.gov/x"), {"ok": True})
        self.assertEqual(len(attempts), 3)
        self.assertIn("tteschon-skills", attempts[0].get_header("User-agent"))

    def test_not_found_is_not_retried(self):
        attempts = self.respond(self.error(404))
        with self.assertRaises(nws.NotFound):
            nws.fetch("https://api.weather.gov/x")
        self.assertEqual(len(attempts), 1)

    def test_gives_up_with_exit_code_3(self):
        self.respond(*[self.error(500)] * (nws.RETRIES + 1))
        with self.assertRaises(nws.Failure) as caught:
            nws.fetch("https://api.weather.gov/x")
        self.assertEqual(caught.exception.code, 3)


if __name__ == "__main__":
    unittest.main(verbosity=1)
