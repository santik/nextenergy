# Home Assistant Integration

To visualize your energy prices in Home Assistant, we will do two things:
1.  **Fetch the Data**: Create a REST sensor that pulls your JSON file.
2.  **Display the Data**: Use `apexcharts-card` (a popular custom card) to graph the prices.

## Prerequisite
You need [ApexCharts Card](https://github.com/RomRider/apexcharts-card) installed (available via HACS).

## 1. configuration.yaml (The Sensor)

Add this to your `configuration.yaml` file (or `sensors.yaml`). This fetches the data every hour.

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

*Restart Home Assistant after adding this.*

## 2. Lovelace Dashboard (The Card)

Add a "Manual" card to your dashboard and paste this configuration:

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: NextEnergy Prices
  show_states: true
  colorize_states: true
graph_span: 24h
span:
  start: day
now:
  show: true
  label: Now
series:
  - entity: sensor.nextenergy_prices
    type: column
    name: Price
    float_precision: 2
    show:
      in_header: true
    data_generator: |
      // The sensor state is the date (YYYY-MM-DD)
      // The attribute 'prices' contains the list of {time, price}
      
      var date = entity.state; 
      // If the sensor hasn't loaded logic yet, return empty
      if (!entity.attributes.prices) return [];

      return entity.attributes.prices.map((record) => {
        // Construct ISO timestamp: "2026-02-02T14:00"
        return [new Date(`${date}T${record.time}`).getTime(), record.price];
      });
```

## Troubleshooting
-   **Sensor not showing attributes?** Check `Developer Tools -> States -> sensor.nextenergy_prices`. It should show a long list under `prices`.
-   **Graph empty?** Ensure `apexcharts-card` is up to date and supports `data_generator`.
