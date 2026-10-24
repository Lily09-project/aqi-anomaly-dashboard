export interface QuantileHour {
  h: number;
  t: string;
  p10: number;
  p50: number;
  p90: number;
}

export interface Station {
  station: string;
  county: string;
  latitude: number;
  longitude: number;
  coordinate_source: string;
  aqi: number;
  pm25: number;
  pm10: number;
  o3: number;
  wind_speed: number;
  category: string;
  category_label: string;
  history: { t: string; aqi: number | null }[];
  forecast: QuantileHour[];
}

export interface Category {
  upper: number;
  key: string;
  label: string;
}

export interface Overview {
  latest: string;
  stations: Station[];
  categories: Category[];
  planner_thresholds: { sensitive: number; general: number };
}

export interface Link {
  upstream: string;
  downstream: string;
  lag_hours: number;
  r: number;
  r_synchronous: number;
  truth_lag: number | null;
}

export interface Propagation {
  max_lag: number;
  min_correlation: number;
  links: Link[];
  nearest_upstream: Record<string, { upstream: string; lag_hours: number }>;
  matrix: Record<string, Record<string, { lag: number; r: number }>>;
  episode: { start: string; end: string; times: string[]; aqi: Record<string, (number | null)[]> };
  ground_truth: Record<string, number> | null;
}

export interface Driver {
  variable: string;
  label: string;
  z: number;
}

export interface AnomalyEvent {
  id: string;
  station: string;
  start: string;
  end: string;
  peak: string;
  duration_hours: number;
  peak_aqi: number;
  peak_pm25: number;
  kind: "local" | "regional";
  drivers: Driver[];
  similar: { event_id: string; distance: number }[];
  context: { t: string; pm25: number | null; baseline: number | null }[];
}

export interface Anomalies {
  threshold: number;
  regional_window_hours: number;
  variables: Record<string, string>;
  events: AnomalyEvent[];
  validation: {
    injected_events: number;
    recall: number;
    local_events: number;
    local_precision: number | null;
    injected_labelled_regional: number;
  } | null;
}

export interface WhatIfInput {
  key: string;
  label: string;
  unit: string;
  min: number;
  max: number;
  default: number;
}

export interface WhatIf {
  inputs: WhatIfInput[];
  feature_order: string[];
  means: number[];
  scales: number[];
  coefficients: number[];
  intercept: number;
  residual_p10: number;
  residual_p90: number;
  calibration_size: number;
  parity_cases: { inputs: Record<string, number>; expected: number }[];
}

export interface HorizonMetrics {
  h: number;
  coverage: number;
  mae: number;
  mae_without_upstream: number;
  persistence_mae: number;
  climatology_mae: number;
  downstream_mae: number | null;
  downstream_mae_without_upstream: number | null;
  interval: [number, number, number];
  test_size: number;
}

export interface Model {
  split: { train_end: string; calibration_end: string; test_end: string };
  features: string[];
  target_coverage: number;
  horizons: HorizonMetrics[];
  downstream_stations: string[];
  drift: { station: string; reference_mean: number; current_mean: number; shift_sd: number | null; status: string }[];
}

export interface Provenance {
  data_source: string;
  is_simulated: boolean;
  provider: string | null;
  seed: number;
  range: { start: string; end: string };
  stations: number;
  rows: number;
  completeness: number | null;
  input_sha256: string | null;
  schema_sha256: string | null;
  injected_events_file: string | null;
  sources: { label: string; url: string }[];
}

export interface Manifest {
  schema_version: string;
  files: Record<string, string>;
}

export interface DataFiles {
  "overview.json": Overview;
  "propagation.json": Propagation;
  "anomalies.json": Anomalies;
  "whatif.json": WhatIf;
  "model.json": Model;
  "provenance.json": Provenance;
}
