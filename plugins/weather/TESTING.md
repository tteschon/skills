# Testing the weather plugin

Three things can break independently, so test them separately.

## 1. The script

```bash
python3 plugins/weather/tests/test_nws.py
```

Runs offline against responses recorded from api.weather.gov in
`tests/fixtures/`. It covers the traps that make raw API output misleading:
Celsius dewpoints in US-unit hourly data, `ends` versus `expires` on alerts,
watches still listed after an upgrade, holiday period names, grid amounts that
straddle local midnight, blank observation fields that the raw METAR still
has, and coordinates that argparse mistakes for options. Run it with Python 3.9
as well as a current one, because the skill promises 3.9:

```bash
uv run --no-project --python 3.9 python plugins/weather/tests/test_nws.py
```

Then run it live. These need `api.weather.gov` and, for the address,
`geocoding.geo.census.gov`:

```bash
S=plugins/weather/skills/us-weather/scripts/nws.py
python3 $S 39.7456,-97.0892                 # Kansas - full default report
python3 $S 39.7456,-97.0892 --date saturday # one day, with totals
python3 $S --address "1600 Pennsylvania Ave NW, Washington, DC 20500" --units si --days 1
python3 $S 21.3069,-157.8583 --days 1       # Honolulu - NOW often comes from the raw METAR
python3 $S -14.2756,-170.702                # American Samoa - zone text forecast only
python3 $S 38.5,-72.0                       # offshore - marine note, exit 0
python3 $S 51.5074,-0.1278                  # London - exit 2
```

To find a place with alerts in effect, list them and pick an area:

```bash
curl -s -H 'User-Agent: (test, https://github.com/tteschon/skills)' \
  'https://api.weather.gov/alerts/active?status=actual' | jq -r '.features[].properties | "\(.event) | \(.areaDesc)"' | head
```

Refresh the fixtures only on purpose. Tests pin "now" to the moment they were
recorded, so new fixtures mean new expected values.

## 2. Triggering

Start a fresh session for each prompt. Once a skill is active in a
conversation the test is worthless.

Should activate:

- What's the weather in Denver this week?
- Is it going to rain in Chicago tomorrow afternoon?
- Is Saturday dry enough to stain the deck? I'm in Lawrence, KS.
- Are there any weather warnings for Tampa right now?
- How cold is it in Anchorage?

Should not activate:

- What's the weather in London? (outside the US)
- How much did it rain in Boston last week? (past weather)
- Build me a weather dashboard app (software work, not a forecast)

## 3. Behaviour

Run one activating prompt and check the answer:

- Names the place the LOCATION line resolved to, and uses that place's local
  time.
- Leads with any alert in effect, with its end time from `Ends`, not the
  message expiry.
- Every number appears in the script's output.
- A planning answer gives the hours that work and the limits it assumed, and
  does not present an invented threshold as fact.
- On exit 3, says the NWS API is unavailable rather than estimating.
