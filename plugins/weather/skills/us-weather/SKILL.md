---
name: us-weather
description: Get US weather from the National Weather Service API (api.weather.gov) - current conditions, the 7-day and hourly forecast, active watches and warnings, and one day's hour-by-hour outlook with rain, snow and gust totals for planning. Use when someone asks about the weather, temperature, rain, snow, wind or storms at a US place, whether a day suits an outdoor plan, or which alerts are in effect. Not for places outside the US, or for past weather.
compatibility: Requires python3 (3.9 or later, standard library only) and HTTPS access to api.weather.gov, plus geocoding.geo.census.gov for street addresses. No API key.
allowed-tools: Bash(python3:*)
---

# US weather

Answers weather questions about US places with `scripts/nws.py` (relative to
this skill's directory). Every number in the answer comes from the script's
output. The answer says which place and which local time it describes, and
leads with any alert in effect.

## Workflow

1. **Resolve** the place to coordinates.
2. **Pick** the mode that matches the question.
3. **Run** the script.
4. **Check** that the LOCATION line names the place asked about.
5. **Answer**, alerts first.

## Find the coordinates

| The user gave | Do this |
|---|---|
| A US street address | `--address "1600 Pennsylvania Ave NW, Washington, DC 20500"` |
| A city, town, ZIP code or landmark | Pass its coordinates from your own knowledge, latitude first, up to 4 decimals |
| No place at all | Ask for a city or ZIP code. Do not guess from a time zone |
| A place outside the US | Not this skill - the API covers only the US and its territories |

The Census geocoder behind `--address` matches street addresses only.
`--address "Denver, CO"` fails, so pass coordinates for a city.

Then read the first line of the output, `LOCATION 39.7456, -97.0892 - 4.2 mi
N of Linn, KS`. It names the nearest place the NWS knows of. If that is not
the place asked about, or a city lies more than about 15 miles off, the
coordinates are wrong. Fix them and run again before answering.

## Pick the mode

| Question | Command |
|---|---|
| "What's the weather?", this week, the forecast | `python3 scripts/nws.py LAT,LON` |
| "What's it like right now?" | Same - read NOW |
| The next few hours, "when does the rain start?" | `--hours 12` (the hourly forecast runs about 6 days) |
| One day, "is Saturday good for X?" | `--date saturday` |
| "Any warnings?", "is a storm coming?" | Default - read ALERTS |
| Celsius and km/h | `--units si` |
| Numbers to compute with | `--json` |

**Let the script work out the date.** `--date` takes `today`, `tomorrow`, a
weekday or `YYYY-MM-DD`, and resolves it in the location's time zone. A
weekday means the next one, today included. Working out "Saturday" yourself
goes wrong near midnight and across time zones.

## Read the output

- **ALERTS** - lead with any alert in effect: the event, when it starts and
  ends, and the headline. Quote the "What to do" line for a warning.
  `NOT CHECKED` means the check failed. Then say alerts could not be checked,
  never that there are none.
- **Times** are the location's local time, not the user's. Say so when the
  user is somewhere else.
- **NOW** is one station's observation, with its distance and age. Mention
  both when the station is more than about 10 miles away or the reading is
  over an hour old. The station is often an airport, and a town in a valley or
  on the coast can differ from it.
- **FORECAST** periods are 12 hours long. A day period runs 6 AM to 6 PM, and
  a night period runs from 6 PM to 6 AM the next morning, so "Saturday Night"
  ends on Sunday. Each period's detail line carries gusts and expected amounts.
- **DAY** summarizes one local calendar day. `Amount` is liquid-equivalent
  precipitation, meaning rain plus melted snow, and `Snow` is snowfall depth.
  `grid only reaches ...` means the total covers only part of the day. For
  today, the hours and totals start at the current hour.

## Answer a planning question

For "is Saturday dry enough to stain the deck?", "can we hike Sunday
morning?" and similar questions:

1. Run `--date` for the day. If the job needs dry time afterwards (stain,
   paint, sealant, fresh concrete, lawn treatments), run it for the next day
   too.
2. Judge the hours the activity needs, not the whole day. A 77% chance at
   6 PM does not spoil a morning job.
3. Take the limits from the product label or the user: minimum temperature,
   hours without rain, maximum wind. If you assume a limit, say which one.
   Do not present an invented threshold as fact.
4. Answer yes, no, or which hours work. Give the figures behind the answer
   and the forecast's issue time.

**A chance of precipitation is not a duration or an intensity.** "40%" is the
chance that at least 0.01 inch falls at the spot during that hour or period.
Pair it with the `Amount`: 40% with 0.02 in is a passing sprinkle, and 40%
with 0.8 in is a real risk of a soaking.

## Troubleshooting

| Symptom | Cause | Do this |
|---|---|---|
| `NWS has no data for ...`, exit 2 | Outside the US, or latitude and longitude swapped | Latitude goes first. US longitudes are negative except in Guam and the Northern Mariana Islands. Outside the US, say this skill cannot help |
| `no match` from `--address` | Not a full street address | Pass coordinates instead |
| `beyond the NWS forecast` | The forecast runs about 7 days | Say so. Do not fill the gap with seasonal averages presented as a forecast |
| `has passed` | The API holds no past forecasts | Say past weather is out of scope here |
| `zone ... text forecast` | No forecast grid, e.g. American Samoa | Answer from the text. Hourly and `--date` figures do not exist there |
| `marine zone` note | The point is offshore | Point to https://www.weather.gov/marine |
| `NOW no recent observation` | Nearby stations are not reporting | Describe the current forecast period instead, and say that is what it is |
| `read from the station's raw METAR` | The API left decoded fields blank | Nothing - the values are the station's own |
| Exit 3 after retries | API outage - they are common and short | Retry once a minute later, then say the NWS API is down. Never answer with remembered or estimated numbers |
| `refused the request`, HTTP 403 | No identifying User-Agent, or a proxy blocks the host | Set `NWS_USER_AGENT="(app-name, contact)"`. In a sandbox, allow `api.weather.gov` |

## Gotchas

- **Use the script rather than calling the API directly.** Raw responses
  have traps that parse cleanly and then mislead: observations are always in
  Celsius and km/h, and the hourly dewpoint is in Celsius even when everything
  else is in Fahrenheit. An alert's `expires` is only when that message will
  be replaced, not when the hazard ends. `/alerts/active` keeps listing a watch
  after it has been upgraded to a warning.

  ```bash
  # WRONG - reports when each message expires, and includes the upgraded watch
  curl -s 'https://api.weather.gov/alerts/active?point=38.8987,-77.0352' | jq '.features[].properties.expires'

  # CORRECT - end times from `ends`, upgraded and cancelled alerts left out
  python3 scripts/nws.py 38.8987,-77.0352
  ```

- **Periods are named after holidays.** On Thanksgiving the forecast says
  "Thanksgiving Day", not "Thursday". Find a day with `--date`, not by
  searching for a period by name.
- **Mention the forecast's age when it is old.** The issue time is printed
  under FORECAST and DAY. If it is more than about 12 hours old, say so in the
  answer, because the API sometimes serves a stale forecast during problems
  upstream.

## Complete example

"Can I stain the deck in Linn, Kansas this Saturday?"

```bash
python3 scripts/nws.py 39.7456,-97.0892 --date saturday
python3 scripts/nws.py 39.7456,-97.0892 --date sunday
```

```
LOCATION  39.7456, -97.0892 - 4.2 mi N of Linn, KS
ALERTS    none in effect
DAY       Saturday 2026-11-28, forecast issued Wed 20:26
  Temp      34°F to 51°F
  Precip    chance peaks at 77% at 18:00
  Amount    0.04 in liquid equivalent, rain and melted snow
  Saturday             High 52°F  precip 14%  wind S 5 mph            Partly Sunny
  Saturday Night       Low 34°F   precip 77%  wind N 5 to 20 mph      Light Rain
  Sat 12:00   49°F    14%   77%   42°F  S 5 mph        Partly Sunny
  Sat 16:00   50°F    14%   71%   41°F  SE 5 mph       Partly Sunny
  Sat 18:00   46°F    77%   83%   41°F  E 5 mph        Light Rain
```

The answer: probably not. It is likely dry until 5 PM, but only 49-51°F from
noon to 4 PM, and light rain is likely from 6 PM - hours after the stain goes
on. Many stains want 50°F or more and a day or two without rain, so check the
label. From the NWS forecast issued Wednesday at 8:26 PM Central.

## References

- https://www.weather.gov/documentation/services-web-api
- https://api.weather.gov/openapi.json
- https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html
- https://www.weather.gov/ffc/pop
