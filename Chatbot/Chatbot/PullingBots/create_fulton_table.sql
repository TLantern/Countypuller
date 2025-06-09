-- Database table for Fulton County GA Lien Index records
-- Run this SQL in your PostgreSQL database before using the scraper

CREATE TABLE IF NOT EXISTS fulton_ga_filing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  case_number TEXT UNIQUE NOT NULL,
  document_type TEXT,
  filing_date TIMESTAMP,
  debtor_name TEXT,
  claimant_name TEXT,
  county TEXT,
  book_page TEXT,
  document_link TEXT,
  state TEXT DEFAULT 'GA',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  is_new BOOLEAN DEFAULT TRUE,
  "userId" TEXT
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_fulton_ga_case_number ON fulton_ga_filing(case_number);
CREATE INDEX IF NOT EXISTS idx_fulton_ga_filing_date ON fulton_ga_filing(filing_date);
CREATE INDEX IF NOT EXISTS idx_fulton_ga_user_id ON fulton_ga_filing("userId");
CREATE INDEX IF NOT EXISTS idx_fulton_ga_county ON fulton_ga_filing(county);
CREATE INDEX IF NOT EXISTS idx_fulton_ga_document_type ON fulton_ga_filing(document_type);

-- Add comments for documentation
COMMENT ON TABLE fulton_ga_filing IS 'Fulton County Georgia lien index records from GSCCCA system';
COMMENT ON COLUMN fulton_ga_filing.case_number IS 'Unique case/document identifier';
COMMENT ON COLUMN fulton_ga_filing.document_type IS 'Type of document (Lien, Lis Pendens, etc.)';
COMMENT ON COLUMN fulton_ga_filing.filing_date IS 'Date the document was filed';
COMMENT ON COLUMN fulton_ga_filing.debtor_name IS 'Name of the debtor/defendant';
COMMENT ON COLUMN fulton_ga_filing.claimant_name IS 'Name of the claimant/plaintiff';
COMMENT ON COLUMN fulton_ga_filing.county IS 'Fulton County (always FULTON for this table)';
COMMENT ON COLUMN fulton_ga_filing.book_page IS 'Book and page reference';
COMMENT ON COLUMN fulton_ga_filing.document_link IS 'URL to document if available'; 