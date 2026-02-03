import asyncio
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
URL = "https://mijn.nextenergy.nl/Website_CW/MarketPrices"

async def run():
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            locale="nl-NL"
        )
        page = await context.new_page()

        # Variable to store captured responses
        captured_responses = []

        # Define response handler
        async def handle_response(response):
            if "DataActionGetDataPoints" in response.url and response.request.method == "POST":
                try:
                    data = await response.json()
                    # Only append if it actually has data points
                    if data.get('data', {}).get('DataPoints', {}).get('List'):
                        print(f"Intercepted energy prices from: {response.url}")
                        captured_responses.append({
                            'data': data,
                            'timestamp': datetime.now().isoformat()
                        })
                except Exception as e:
                    print(f"Error parsing JSON: {e}")

        # Listen for the specific response
        page.on("response", handle_response)

        print(f"Navigating to {URL}...")
        await page.goto(URL, wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # Try to click "Next" to get tomorrow's prices
        print("Clicking 'Next' for tomorrow's prices...")
        try:
            next_button = page.locator("#b1-b3-b1-Next")
            if await next_button.is_visible():
                await next_button.click()
                await page.wait_for_timeout(3000)
            else:
                print("Next button not found or not visible.")
        except Exception as e:
            print(f"Could not click next button: {e}")

        if captured_responses:
            print(f"Processing {len(captured_responses)} days of data...")
            all_parsed_points = []
            
            # Use the date from the capture timestamp for the first one as "Today"
            # and +1 day for subsequent ones if they exist.
            # However, a safer way is to peek at the dates if they were in the JSON,
            # but since they aren't clearly labeled in the points, we use the fetch context.
            from datetime import timedelta
            start_date = datetime.now()

            for i, response_obj in enumerate(captured_responses):
                try:
                    current_date = start_date + timedelta(days=i)
                    date_str = current_date.strftime("%Y-%m-%d")
                    
                    raw_data = response_obj['data']
                    points = raw_data.get('data', {}).get('DataPoints', {}).get('List', [])
                    day_parsed_points = []
                    
                    for p in points:
                        try:
                            label_int = int(p.get('Label'))
                            hour = (label_int) % 24
                            price = float(p.get('Value'))
                            time_str = f"{hour:02d}:00"
                            # Add date to the record
                            day_parsed_points.append({
                                "date": date_str,
                                "time": time_str, 
                                "price": price
                            })
                        except (ValueError, TypeError):
                            continue
                    
                    if not day_parsed_points:
                        continue

                    all_parsed_points.extend(day_parsed_points)
                    
                    # Ensure output directory exists
                    output_dir = os.path.join(OUTPUT_DIR, "data")
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # Save individual day file
                    parsed_filename = os.path.join(output_dir, f"parsed_energy_prices_{date_str}.json")
                    print(f"Saving {date_str} data to {parsed_filename}...")
                    with open(parsed_filename, 'w', encoding='utf-8') as f:
                        json.dump(day_parsed_points, f, indent=2)

                except Exception as e:
                    print(f"Error parsing day {i}: {e}")

            # Save combined 'latest' file
            if all_parsed_points:
                output_dir = os.path.join(OUTPUT_DIR, "data")
                latest_filename = os.path.join(output_dir, "latest_energy_prices.json")
                print(f"Updating combined latest file at {latest_filename}...")
                
                latest_data = {
                    "meta": {
                        "fetch_time": datetime.now().isoformat(),
                        "today": start_date.strftime("%Y-%m-%d")
                    },
                    "prices": all_parsed_points
                }
                
                with open(latest_filename, 'w', encoding='utf-8') as f:
                    json.dump(latest_data, f, indent=2)

                print("Done successfully.")
        else:
            print("No data was captured from the API.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
