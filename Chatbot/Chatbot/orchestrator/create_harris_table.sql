-- Create Harris County filing table for enriched records
-- This table stores records processed by the Harris County agent with AI summaries

CREATE TABLE IF NOT EXISTS harris_county_filing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_number TEXT UNIQUE NOT NULL,
  filing_date TIMESTAMP,
  doc_type TEXT DEFAULT 'L/P',
  subdivision TEXT,
  section TEXT,
  block TEXT,
  lot TEXT,
  property_address TEXT,
  parcel_id TEXT,
  ai_summary TEXT,
  county TEXT DEFAULT 'Harris',
  state TEXT DEFAULT 'TX',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  is_new BOOLEAN DEFAULT TRUE,
  "userId" TEXT NOT NULL
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_harris_county_filing_user_id ON harris_county_filing("userId");
CREATE INDEX IF NOT EXISTS idx_harris_county_filing_case_number ON harris_county_filing(case_number);
CREATE INDEX IF NOT EXISTS idx_harris_county_filing_filing_date ON harris_county_filing(filing_date);
CREATE INDEX IF NOT EXISTS idx_harris_county_filing_parcel_id ON harris_county_filing(parcel_id);
CREATE INDEX IF NOT EXISTS idx_harris_county_filing_county ON harris_county_filing(county);

-- Add foreign key constraint to User table (if needed)
-- ALTER TABLE harris_county_filing ADD CONSTRAINT fk_harris_county_filing_user 
--   FOREIGN KEY ("userId") REFERENCES "User"(id) ON DELETE CASCADE;

-- Add comments for documentation
COMMENT ON TABLE harris_county_filing IS 'Harris County enriched records with AI property summaries';
COMMENT ON COLUMN harris_county_filing.case_number IS 'Unique case identifier from Harris County';
COMMENT ON COLUMN harris_county_filing.filing_date IS 'Date the lis pendens was filed';
COMMENT ON COLUMN harris_county_filing.doc_type IS 'Document type (L/P for Lis Pendens)';
COMMENT ON COLUMN harris_county_filing.subdivision IS 'Property subdivision name';
COMMENT ON COLUMN harris_county_filing.section IS 'Property section number';
COMMENT ON COLUMN harris_county_filing.block IS 'Property block number';
COMMENT ON COLUMN harris_county_filing.lot IS 'Property lot number';
COMMENT ON COLUMN harris_county_filing.property_address IS 'Full property address from HCAD lookup';
COMMENT ON COLUMN harris_county_filing.parcel_id IS 'HCAD parcel/account number';
COMMENT ON COLUMN harris_county_filing.ai_summary IS 'AI-generated property analysis summary';
COMMENT ON COLUMN harris_county_filing."userId" IS 'User ID who owns this record'; 