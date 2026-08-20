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
