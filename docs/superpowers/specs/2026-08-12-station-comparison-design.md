# Station Comparison Decision View Design

## Goal

Add a consumer-facing station comparison workflow that helps a user compare up to three Taiwan AQI stations using current observations, next-hour forecasts, calibrated uncertainty, station-specific historical context, and anomaly evidence.

## Chosen Direction

The Dashboard will add a sixth tab named `地區比較`. This is preferred over local-only alert preferences and model drift monitoring because it creates immediate user value with the data already produced by the project, while remaining credible in Sample Data mode.

## Product Rules

- Users can compare two or three stations at a time.
- The comparison uses each station's latest observation and displays its timestamp explicitly.
- A station is considered comparable when its observation is no more than two hours older than the newest selected station.
- The recommended station is the comparable station with the lowest next-hour point forecast. If a forecast is unavailable, current AQI is used.
- The recommendation must state its basis and must never be described as an official alert, medical recommendation, route recommendation, or guaranteed future outcome.
- Sample Data remains visibly labeled as simulated data.
- Internal model features and targets are not exposed in the comparison download.

## Data Contract

Create `src/station_comparison.py` with:

- `build_station_comparison(features, predictions=None, anomalies=None, selected_sites=None, stale_after_hours=2, reference_features=None) -> pd.DataFrame`
- `choose_recommended_station(comparison) -> dict[str, object]`
- `export_comparison_csv(comparison) -> bytes`

The comparison table contains station identity, county, observation time, lag hours, freshness state, current AQI and category, PM2.5, next-hour point forecast, 80% interval, forecast change, station-specific same-hour baseline, change versus baseline, recent six-hour change, attention context, anomaly flag, and anomaly evidence. `reference_features` is optional history used only for station-specific context. Optional history, prediction and anomaly inputs must degrade to missing values without raising errors.

## Interface

The `地區比較` tab contains:

1. A station multi-select with a maximum of three selections.
2. A recommendation band that explains the selected station and whether the basis is the next-hour forecast or current AQI.
3. One compact card per station with current AQI, category, forecast and observation time.
4. A current-versus-forecast grouped bar chart.
5. A 24-hour AQI trend chart for the selected stations.
6. A formal comparison table and UTF-8 BOM CSV download.
7. A visible limitation note covering Sample Data, stale observations, forecast uncertainty, and official information.

The visual direction remains an industrial environmental monitoring console: dark navy surfaces, strong white text, orange for decision emphasis, blue for forecast context, restrained borders, and no decorative illustration.

## Error Handling

- Fewer than two selected stations: show a clear prompt and do not render a recommendation.
- Missing observations: return an empty comparison and show an informational state.
- Missing forecasts: use current AQI as the recommendation basis.
- Stale stations: label them and exclude them from recommendation candidates.
- All stations stale relative to the newest observation is impossible by construction; if the data contract is malformed, return no recommendation.

## Testing

- Verify station rows never mix observations between stations.
- Verify only the latest row per station is used.
- Verify exact station and timestamp matching for forecasts and anomalies.
- Verify stale stations are excluded from recommendation.
- Verify forecast fallback to current AQI.
- Verify missing optional inputs and empty frames are safe.
- Verify exported CSV excludes internal fields and opens correctly in Chinese Excel.
- Extend app import tests to enforce the tab, consumer copy and responsive comparison CSS.
- Run the full sample pipeline, smoke test, pytest, dependency audit, desktop browser review and 390px mobile review.

## Scope Boundaries

This feature does not add accounts, persistent preferences, push notifications, route planning, geolocation, pollution-source attribution, medical advice, or new external APIs.
