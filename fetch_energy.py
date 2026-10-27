import asyncio
import json
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(OUTPUT_DIR, "data")
URL = "https://mijn.nextenergy.nl/Website_CW/MarketPrices"
ENDPOINT = "/Website_CW/screenservices/Website_CW/Blocks/WB_EnergyPrices/DataActionGetDataPoints"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)

# The MarketPrices page serves every series through one data-action, selected
# by the request's `Filter`. We fetch two electricity price levels:
#   - import  -> CostsLevel "TotalPrice"  incl. VAT (what you pay)
#   - export  -> CostsLevel "MarketPrice" excl. VAT (feed-in / spot price)
# Gas is not an hourly series; it comes back as the scalar `CurrentGasPrice`
# field on the (TotalPrice) response as a single daily price.

# JS replay helper: fires each job from the page context so the OutSystems
# session cookies are reused; only the CSRF token and Filter need supplying.
REPLAY_JS = """async ([endpoint, token, template, jobs, hour]) => {
    const out = [];
    for (const job of jobs) {
        const body = JSON.parse(JSON.stringify(template));
        body.screenData.variables.Filter.CostsLevel = job.costsLevel;
        body.screenData.variables.Filter.PriceIncludingVAT = job.vat;
        body.screenData.variables.Filter.PriceDate = job.date;
        body.screenData.variables.Filter.CurrentHour = hour;
        try {
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json; charset=UTF-8',
                    'Accept': 'application/json',
                    'OutSystems-locale': 'nl-NL',
                    'X-CSRFToken': token
                },
                body: JSON.stringify(body),
                credentials: 'include'
            });
            const j = await res.json();
            out.push({
                job,
                status: res.status,
                data: j.data || null,
                exception: j.exception ? (j.exception.message || 'error') : null
            });
        } catch (e) {
            out.push({ job, error: String(e) });
        }
    }
    return out;
}"""


def parse_hourly(data):
    """Map a DataPoints list to {time: price}. The hour is the point's INDEX
    in the list (the chart's x-axis order, confirmed by the Tooltip "Nu"),
    not the `Label` field."""
    points = (data.get("DataPoints") or {}).get("List") or []
    day = {}
    for i, pt in enumerate(points):
        try:
            day[f"{i:02d}:00"] = float(pt.get("Value"))
        except (ValueError, TypeError):
            continue
    return day


async def run():
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    tomorrow_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")

    # Early check: do we already have tomorrow's data?
    latest_filename = os.path.join(DATA_DIR, "latest_energy_prices.json")
    if os.path.exists(latest_filename):
        try:
            with open(latest_filename, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            if any(p.get("date") == tomorrow_str for p in existing_data.get("prices", [])):
                print(f"Tomorrow's data ({tomorrow_str}) already present. Skipping fetch.")
                return
        except Exception as e:
            print(f"Could not read existing data (continuing with fetch): {e}")

    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT, locale="nl-NL")
        page = await context.new_page()

        # Capture the first data-action request to reuse its CSRF token + body.
        captured = {}

        def handle_request(request):
            if "DataActionGetDataPoints" in request.url and request.method == "POST":
                if "body" not in captured:
                    token = request.headers.get("x-csrftoken")
                    body = request.post_data
                    if token and body:
                        captured["token"] = token
                        captured["body"] = body
                        print("Captured request template and CSRF token.")

        page.on("request", handle_request)

        print(f"Navigating to {URL}...")
        await page.goto(URL, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        if "body" not in captured:
            print("Failed to capture request template/token; aborting.")
            await browser.close()
            return

        template = json.loads(captured["body"])
        token = captured["token"]

        jobs = [
            {"key": "import", "date": today_str, "costsLevel": "TotalPrice", "vat": True},
            {"key": "import", "date": tomorrow_str, "costsLevel": "TotalPrice", "vat": True},
            {"key": "export", "date": today_str, "costsLevel": "MarketPrice", "vat": False},
            {"key": "export", "date": tomorrow_str, "costsLevel": "MarketPrice", "vat": False},
        ]

        print(f"Requesting {len(jobs)} series...")
        results = await page.evaluate(
            REPLAY_JS, [ENDPOINT, token, template, jobs, today.hour]
        )

        await browser.close()

    # Parse results into import (hourly), export (hourly), gas (daily).
    import_prices = {}  # date -> {time: price}
    export_prices = {}  # date -> {time: price}
    gas_prices = {}     # date -> price

    for r in results:
        job = r.get("job", {})
        if r.get("error") or r.get("exception") or not r.get("data"):
            print(f"Skipping {job.get('key')} {job.get('date')}: "
                  f"{r.get('error') or r.get('exception') or 'no data'}")
            continue

        data = r["data"]
        day = parse_hourly(data)

        if job["key"] == "import":
            if day:
                import_prices[job["date"]] = day
            # Gas comes as a scalar on the TotalPrice response (one price/day).
            try:
                gas = float(data.get("CurrentGasPrice"))
                if gas > 0:
                    gas_prices[job["date"]] = gas
            except (ValueError, TypeError):
                pass
        else:
            if day:
                export_prices[job["date"]] = day

    # Merge import + export into one chronological price list.
    all_prices = []
    for date in sorted(import_prices.keys()):
        for time in sorted(import_prices[date].keys()):
            rec = {"date": date, "time": time, "price": import_prices[date][time]}
            export = export_prices.get(date, {}).get(time)
            if export is not None:
                rec["export_price"] = export
            all_prices.append(rec)

    gas_list = [{"date": d, "price": gas_prices[d]} for d in sorted(gas_prices.keys())]

    if not all_prices:
        print("No data was captured from the API.")
        return

    os.makedirs(DATA_DIR, exist_ok=True)

    # Per-day history files (import + export merged).
    for date in sorted(import_prices.keys()):
        day_records = [r for r in all_prices if r["date"] == date]
        parsed_filename = os.path.join(DATA_DIR, f"parsed_energy_prices_{date}.json")
        print(f"Saving {date} data to {parsed_filename}...")
        with open(parsed_filename, "w", encoding="utf-8") as f:
            json.dump(day_records, f, indent=2)

    # Combined 'latest' file.
    latest_data = {
        "meta": {
            "fetch_time": datetime.now().isoformat(),
            "today": today_str,
        },
        "prices": all_prices,
        "gas": gas_list,
    }
    print(f"Updating combined latest file at {latest_filename}...")
    with open(latest_filename, "w", encoding="utf-8") as f:
        json.dump(latest_data, f, indent=2)

    print("Done successfully.")


if __name__ == "__main__":
    asyncio.run(run())
