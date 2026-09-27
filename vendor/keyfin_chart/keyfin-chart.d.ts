export interface Envelope {
  id: string;
  label: string;
  budget: number | null;
  current: number | null;
  /** Period-end TOTAL, not an amount to stack on top of current. */
  forecast: number | null;
}
export interface QuantilePoint {
  date: string;
  p10_krw?: number | null;
  p50_krw: number | null;
  p90_krw?: number | null;
}
export interface Balance {
  kind: 'cumulative_expense' | 'total_assets' | 'cash_balance' | 'resource_change';
  /** Budget for the entire selected period; not an asset-balance target. */
  budget_krw?: number | null;
  coverage?: string;
  current_krw: number | null;
  terminal: Omit<QuantilePoint, 'date'>;
  baseline_p50_krw?: number | null;
  history?: Array<{date: string; value_krw: number | null}>;
  forecast?: QuantilePoint[];
  baseline?: QuantilePoint[];
  max_gap_days?: number;
  /** Optional supplied daily amounts in the same order as Result.categories. */
  daily?: Array<{date: string; amounts_krw: number[]}>;
}
export interface Result {
  schema_version?: '2.0';
  id?: string;
  question?: string;
  answer?: string;
  source?: string;
  totalBudget?: number | null;
  totalCurrent?: number | null;
  /** Current amount not assigned to a category; included in totalCurrent. */
  unallocatedCurrent?: number | null;
  /** Preserve joint-path P50 when supplied. */
  totalForecast?: number | null;
  value_semantics?: 'period_total' | 'snapshot' | 'future_only';
  /** Omit to avoid inventing a total from marginal forecasts. */
  forecastAggregation?: 'sum' | 'joint_p50';
  categories: Envelope[];
  meta?: {
    /** Inclusive monthly budget start. Clamps the next boundary to a valid calendar day. */
    period_start?: string;
    as_of?: string;
    /** Inclusive end. Derived from period_start; conflicting supplied ends are rejected. */
    horizon_end?: string;
    [key: string]: unknown;
  };
  balance?: Balance | null;
}
export interface Options {
  style?: Record<string, number>;
  currentOnly?: boolean;
  labelMode?: 'current' | 'forecast';
  /** reference: 0–100% visual cap; linear: shared scale including all finite ratios, up to maxScale. */
  scale?: 'reference' | 'linear';
  /** linear 축의 최대 비율(1 = 100%). 기본 1.2(120%). 넘는 막대는 잘리고 수치는 원래 값으로 표시한다. */
  maxScale?: number;
  onSelect?: (row: Envelope) => void;
}
export interface Controller {
  update(next: Result | Record<string, unknown>): Result;
  setOptions(next: Options): void;
  getData(): Result;
  destroy(): void;
}
export function mount(root: HTMLElement, input: Result | Record<string, unknown>, options?: Options): Controller;
export function cardSvg(input: Result | Record<string, unknown>, style?: Record<string, number>, options?: Options): string;
export function normalize(input: Result | Record<string, unknown>): Result;
export function budgetPeriod(meta: NonNullable<Result['meta']>): NonNullable<Result['meta']>;
/** Shared palette for category bars and daily category composition. */
export const categoryColors: string[];
