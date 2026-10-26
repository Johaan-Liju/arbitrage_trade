import type { Contract, Price } from "./types";
export type SignalStatus = "Investigate" | "No signal" | "Insufficient data";
export type PairEvent = {
  trading_date: string; decision_at: string; normalized_a: number; normalized_b: number;
  raw_pair_spread: number | null; expected_basis: number | null;
  prior_mean: number | null; prior_std: number | null; sample_count: number; cutoff: string; baseline: number | null;
  difference: number | null; z_score: number | null; upper_z: number; lower_z: number;
  status: SignalStatus; reason: string; history_count: number; quality_reasons: string[];
  a: Price; b: Price; age_hours: number;
};
export type PairResult = { basis_differences: {field: string; left: unknown; right: unknown}[]; normalization_issues: {trading_date: string; code: string; reason: string}[];
  pair_id: string; status: SignalStatus; reason: string;
  dataset: string; label: string; as_of: string; spec_a: Contract; spec_b: Contract;
  alignment: string; expiry_difference_days: number; cautions: string[];
  method: { lookback: number; min_observations: number; entry_z: number; basis: string };
  history: PairEvent[]; latest: PairEvent | null;
  quality: { missing_dates: { trading_date: string; reason: string }[]; calendar: string; no_forward_fill: boolean };
};
