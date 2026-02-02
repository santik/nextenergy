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
    value_template: "{{ value_json.meta.date }}"
    json_attributes:
      - prices
      - meta
```

## 2. Native Dashboard Options

### Option A: Visual Markdown Table (Timezone Aware)
Add a **Markdown Card** to your dashboard. This version converts the UTC times from the file into your **local time**.

```yaml
{% raw %}
type: markdown
content: >
  ### Energy Prices (Local Time)
  | Time | Price | Status |
  |:---:|:---:|:---:|
  {% set date = state_attr('sensor.nextenergy_prices', 'meta').date %}
  {% set now_local = now().strftime('%H:00') %}
  {% for item in state_attr('sensor.nextenergy_prices', 'prices') %}
    {%- set utc_time = date ~ "T" ~ item.time ~ "Z" -%}
    {%- set local_dt = utc_time | as_datetime | as_local -%}
    {%- set local_hour = local_dt.strftime('%H:00') -%}
  | {{ '**' if local_hour == now_local else '' }}{{ local_hour }}{{ '**' if local_hour == now_local else '' }} | {{ '%.2f'|format(item.price) }} | {{ '🔴' if item.price > 0.28 else '🟢' if item.price < 0.25 else '🟡' }} |
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
          {% set date = state_attr('sensor.nextenergy_prices', 'meta').date %}
          {% set prices = state_attr('sensor.nextenergy_prices', 'prices') %}
          {% if prices %}
            {# Find the record where local conversion matches current local hour #}
            {% set now_local_hour = now().hour %}
            {% set ns = namespace(found=none) %}
            {% for item in prices %}
              {% set item_local_hour = (date ~ "T" ~ item.time ~ "Z") | as_datetime | as_local | attr('hour') %}
              {% if item_local_hour == now_local_hour %}
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

## Troubleshooting
- **Missing Data**: Check **Developer Tools > States** and look for `sensor.nextenergy_prices`. 
- **Time Offset**: If the times are still off, ensure your Home Assistant System Timezone is correctly set in **Settings > System > General**.


*Restart Home Assistant after adding the sensors to your configuration.*
