-- Brokers table
CREATE TABLE IF NOT EXISTS brokers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    area TEXT,
    city TEXT DEFAULT 'Bangalore',
    phone TEXT,
    email TEXT,
    source TEXT,                        -- which portal they were found on

    -- Profile links
    website_url TEXT,
    magicbricks_url TEXT,
    acres99_url TEXT,
    housing_url TEXT,
    nobroker_url TEXT,
    justdial_url TEXT,
    google_maps_url TEXT,
    linkedin_url TEXT,
    instagram_url TEXT,

    -- Raw scraped data (JSONB for flexibility)
    website_data JSONB,
    social_data JSONB,
    portal_data JSONB,
    google_business_data JSONB,
    linkedin_data JSONB,
    instagram_data JSONB,

    -- Scores (out of max shown in comments)
    score_website INTEGER DEFAULT 0,        -- /30
    score_social_media INTEGER DEFAULT 0,   -- /20
    score_linkedin INTEGER DEFAULT 0,       -- /10
    score_google_business INTEGER DEFAULT 0, -- /15
    score_property_portals INTEGER DEFAULT 0, -- /15
    score_listings INTEGER DEFAULT 0,       -- /5
    score_video INTEGER DEFAULT 0,          -- /5
    total_score INTEGER DEFAULT 0,          -- /100

    -- AI insights
    strengths TEXT,
    weaknesses TEXT,
    missed_opportunities TEXT,
    sales_pitch TEXT,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_scraped_at TIMESTAMPTZ
);

-- Deduplicate on phone or name+area combo
CREATE UNIQUE INDEX IF NOT EXISTS brokers_phone_idx ON brokers(phone) WHERE phone IS NOT NULL;
CREATE INDEX IF NOT EXISTS brokers_area_idx ON brokers(area);
CREATE INDEX IF NOT EXISTS brokers_total_score_idx ON brokers(total_score DESC);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER brokers_updated_at
    BEFORE UPDATE ON brokers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
