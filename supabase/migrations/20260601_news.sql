CREATE TABLE IF NOT EXISTS fs_articles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text UNIQUE NOT NULL,
    source text NOT NULL,
    source_site text NOT NULL,
    published_at timestamptz,
    category text NOT NULL CHECK (category IN ('competition_report', 'injury', 'transfer', 'rule_change', 'general')),
    summary text,
    related_fencer_ids uuid[],
    content_hash text,
    metadata jsonb DEFAULT '{}',
    scraped_at timestamptz DEFAULT now()
);
