PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS businesses (
    business_id INTEGER PRIMARY KEY,
    business_name TEXT NOT NULL,
    industry TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    business_id INTEGER NOT NULL REFERENCES businesses(business_id),
    external_customer_key TEXT NOT NULL,
    segment TEXT NOT NULL,
    region TEXT,
    tenure_months INTEGER NOT NULL,
    preferred_contact_hour INTEGER NOT NULL,
    consent_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id INTEGER PRIMARY KEY,
    business_id INTEGER NOT NULL REFERENCES businesses(business_id),
    campaign_name TEXT NOT NULL,
    offer_type TEXT NOT NULL,
    send_date TEXT NOT NULL,
    send_hour INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    delivery_status TEXT NOT NULL,
    responded INTEGER NOT NULL CHECK (responded IN (0, 1)),
    converted INTEGER NOT NULL CHECK (converted IN (0, 1)),
    sent_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_campaign ON messages(campaign_id);
CREATE INDEX IF NOT EXISTS idx_messages_customer ON messages(customer_id);
