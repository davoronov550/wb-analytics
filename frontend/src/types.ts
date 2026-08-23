export type OrderableField = "price" | "sale_price" | "rating" | "reviews_count" | "name";

export interface Product {
  wb_id: number;
  name: string;
  price: string;
  sale_price: string;
  discount_abs: string;
  discount_pct: number;
  rating: string;
  reviews_count: number;
  query: string | null;
  updated_at: string | null;
}

export interface Filters {
  minPrice?: number;
  maxPrice?: number;
  minRating?: number;
  minReviews?: number;
  query?: string;
}

export interface Sort {
  field: OrderableField;
  descending: boolean;
}

export interface ProductsResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Product[];
}

export type ParseState = "pending" | "running" | "done" | "failed";

export interface ParseAccepted {
  task_id: string;
  query: string;
  status: string;
}

export interface TaskStatus {
  task_id: string;
  query: string;
  status: ParseState;
  created: number;
  updated: number;
  collected_count: number;
  error: string | null;
  finished_at: string | null;
}

export interface Schedule {
  id: number;
  query: string;
  spec: string;
  interval_seconds: number;
  active: boolean;
  last_run_at: string | null;
}

export interface User {
  id: number;
  username: string;
  email?: string | null;
  /** Identity providers linked to this account, e.g. ["password", "google"]. */
  providers?: string[];
}

export interface SavedSearch {
  id: number;
  name: string;
  query: string;
  filters: Record<string, unknown>;
}

export interface PriceSnapshot {
  captured_at: string;
  price: string;
  sale_price: string;
  rating: string;
}

export interface PriceHistory {
  wb_id: number;
  points: PriceSnapshot[];
}

export interface TopProduct {
  wb_id: number;
  name: string;
  reviews_count: number;
}

export interface Stats {
  count: number;
  avg_price: string;
  median_price: string;
  price_stddev: string;
  avg_discount_abs: string;
  discount_share: number;
  top_by_reviews: TopProduct[];
}
