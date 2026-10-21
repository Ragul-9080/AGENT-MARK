export const API_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export const ACCESS_COOKIE = "ama_access";
export const REFRESH_COOKIE = "ama_refresh";

export const ACCESS_COOKIE_MAX_AGE = 60 * 15;
export const REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7;
