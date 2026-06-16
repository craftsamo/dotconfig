-- 0003: fx_rates — cached JPY-per-unit exchange rates for auto-filling reporting_amount.
-- rate = JPY per 1 unit of `currency`, so reporting_value(JPY) = amount_value * rate.
-- Populated by `hb fx-refresh` (public API, no key). Read by `hb add` for non-JPY drafts.
CREATE TABLE fx_rates (
  date       TEXT NOT NULL,                 -- YYYY-MM-DD the rate applies to
  base       TEXT NOT NULL DEFAULT 'JPY',
  currency   TEXT NOT NULL REFERENCES currencies(code),
  rate       TEXT NOT NULL,                 -- decimal string: JPY per 1 unit of `currency`
  source     TEXT NOT NULL,                 -- e.g. exchange_api:open.er-api.com
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (date, base, currency)
);
CREATE INDEX ix_fx_currency_date ON fx_rates(currency, date);
