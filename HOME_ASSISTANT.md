# Home Assistant Native Integration

This guide explains how to visualize energy prices using only **standard Home Assistant functionality** (no third-party plugins or HACS required).

## 1. configuration.yaml (Data Fetching)

Add this REST sensor to your `configuration.yaml`. It fetches the daily data and stores the prices in an attribute.

```yaml
sensor:
  - platform: rest
    name: NextEnergy Prices
    unique_id: nextenergy_prices
    resource: https://santik.github.io/nextenergy/data/latest_energy_prices.json
    scan_interval: 3600
    value_template: "{{ value_json.meta.today }}"
    json_attributes:
      - prices
      - gas
      - meta
```

Each entry in `prices` now carries both the consumption price and the feed-in price:

```json
{ "date": "2026-10-27", "time": "18:00", "price": 0.47, "export_price": 0.28 }
```

- `price` — import / consumption price, **total incl. VAT** (€/kWh)
- `export_price` — feed-in / teruglevering price, **market price excl. VAT** (€/kWh)

`gas` is a separate list with one entry per day (the daily gas price from 06:00, €/m³):

```json
"gas": [ { "date": "2026-10-27", "price": 1.95 } ]
```

## 2. Native Dashboard Options

### Option A: Visual Markdown Table (Timezone Aware)
Add a **Markdown Card** to your dashboard. This version converts the UTC times from the file into your **local time**.

```yaml
{% raw %}
type: markdown
content: >
  ### Energy Prices (Local Time)
  | Time | Import | Export | Status |
  |:---:|:---:|:---:|:---:|
  {% for item in state_attr('sensor.nextenergy_prices', 'prices') %}
    {%- set utc_time = item.date ~ "T" ~ item.time ~ "Z" -%}
    {%- set local_dt = utc_time | as_datetime | as_local -%}
    {%- set local_hour = local_dt.strftime('%H:00') -%}
    {%- set local_date = local_dt.strftime('%Y-%m-%d') -%}
  | {{ '**' if local_hour == now_local and local_date == now().strftime('%Y-%m-%d') else '' }}{{ local_hour }}{{ '**' if local_hour == now_local and local_date == now().strftime('%Y-%m-%d') else '' }} | {{ '%.2f'|format(item.price) }} | {{ '%.2f'|format(item.export_price) if item.export_price is defined else '—' }} | {{ '🔴' if item.price > 0.28 else '🟢' if item.price < 0.25 else '🟡' }} |
  {%- endfor %}
{% endraw %}
```

### Option B: Current Price Sensor (UTC to Local)
Add this **Template Sensor** to your `configuration.yaml`. It finds the price matching your current local hour.

```yaml
{% raw %}
template:
  - sensor:
      - name: "Current Energy Price"
        unique_id: current_energy_price
        unit_of_measurement: "€/kWh"
        state: >
          {% set prices = state_attr('sensor.nextenergy_prices', 'prices') %}
          {% if prices %}
            {# Find the record where local conversion matches current local time #}
            {% set now_utc = now().astimezone(as_utc()) %}
            {% set ns = namespace(found=none) %}
            {% for item in prices %}
              {% set item_utc = (item.date ~ "T" ~ item.time ~ "Z") | as_datetime | as_utc %}
              {% if item_utc <= now_utc < item_utc + timedelta(hours=1) %}
                {% set ns.found = item.price %}
              {% endif %}
            {% endfor %}
            {{ ns.found if ns.found is not none else 'unavailable' }}
          {% else %}
            unavailable
          {% endif %}
{% endraw %}
```

After adding this, you can use the standard **Gauge Card** pointing to `sensor.current_energy_price`.

### Option C: Current Export Price Sensor
Same as Option B, but reads `export_price` (the feed-in / teruglevering value).

```yaml
{% raw %}
template:
  - sensor:
      - name: "Current Export Price"
        unique_id: current_export_price
        unit_of_measurement: "€/kWh"
        state: >
          {% set prices = state_attr('sensor.nextenergy_prices', 'prices') %}
          {% if prices %}
            {% set now_utc = now().astimezone(as_utc()) %}
            {% set ns = namespace(found=none) %}
            {% for item in prices %}
              {% set item_utc = (item.date ~ "T" ~ item.time ~ "Z") | as_datetime | as_utc %}
              {% if item_utc <= now_utc < item_utc + timedelta(hours=1) and item.export_price is defined %}
                {% set ns.found = item.export_price %}
              {% endif %}
            {% endfor %}
            {{ ns.found if ns.found is not none else 'unavailable' }}
          {% else %}
            unavailable
          {% endif %}
{% endraw %}
```

### Option D: Today's Gas Price Sensor
Gas is a single daily price (€/m³), so this just picks today's entry from the `gas` list.

```yaml
{% raw %}
template:
  - sensor:
      - name: "Gas Price Today"
        unique_id: gas_price_today
        unit_of_measurement: "€/m³"
        state: >
          {% set gas = state_attr('sensor.nextenergy_prices', 'gas') %}
          {% if gas %}
            {% set today = now().strftime('%Y-%m-%d') %}
            {% set ns = namespace(found=none) %}
            {% for item in gas %}
              {% if item.date == today %}{% set ns.found = item.price %}{% endif %}
            {% endfor %}
            {{ ns.found if ns.found is not none else 'unavailable' }}
          {% else %}
            unavailable
          {% endif %}
{% endraw %}
```

## Troubleshooting
- **Missing Data**: Check **Developer Tools > States** and look for `sensor.nextenergy_prices`. 
- **Time Offset**: If the times are still off, ensure your Home Assistant System Timezone is correctly set in **Settings > System > General**.


*Restart Home Assistant after adding the sensors to your configuration.*
