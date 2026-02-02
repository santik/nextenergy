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

        # Variable to store the captured response
        captured_data = {}

        # Define response handler
        async def handle_response(response):
            if "DataActionGetDataPoints" in response.url and response.request.method == "POST":
                try:
                    print(f"Intercepted response from: {response.url}")
                    data = await response.json()
                    captured_data['response'] = data
                    captured_data['timestamp'] = datetime.now().isoformat()
                except Exception as e:
                    print(f"Error parsing JSON: {e}")

        # Listen for the specific response
        page.on("response", handle_response)

        print(f"Navigating to {URL}...")
        await page.goto(URL, wait_until="networkidle")
        
        # Wait a bit to ensure potential lazy loaded requests fire
        await page.wait_for_timeout(5000)

        # Generate filename with current date
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = os.path.join(OUTPUT_DIR, f"energy_prices_{date_str}.json")

        if 'response' in captured_data:
            print(f"Data captured successfully. Parsing...")
            try:
                raw_data = captured_data['response']
                points = raw_data.get('data', {}).get('DataPoints', {}).get('List', [])
                parsed_points = []
                for p in points:
                    try:
                        # Label 23 corresponds to 00:00 (0u), Label 0 to 01:00 (1u)
                        label_int = int(p.get('Label'))
                        hour = (label_int + 1) % 24
                        price = float(p.get('Value'))
                        time_str = f"{hour:02d}:00"
                        parsed_points.append({"time": time_str, "price": price})
                    except (ValueError, TypeError):
                        continue
                
                # Ensure output directory exists
                output_dir = os.path.join(OUTPUT_DIR, "data")
                os.makedirs(output_dir, exist_ok=True)
                
                parsed_filename = os.path.join(output_dir, f"parsed_energy_prices_{date_str}.json")
                print(f"Saving parsed data to {parsed_filename}...")
                with open(parsed_filename, 'w', encoding='utf-8') as f:
                    json.dump(parsed_points, f, indent=2)
                
                # Save as latest
                latest_filename = os.path.join(output_dir, "latest_energy_prices.json")
                print(f"Updating latest file at {latest_filename}...")
                with open(latest_filename, 'w', encoding='utf-8') as f:
                    json.dump(parsed_points, f, indent=2)

                print("Done.")
            except Exception as e:
                print(f"Error during parsing: {e}")
        else:
            print("No data was captured from the API.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
