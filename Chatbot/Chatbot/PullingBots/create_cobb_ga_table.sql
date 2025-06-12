-- Create table for Cobb GA filing records
-- This table stores static CSV data for demonstration purposes

DROP TABLE IF EXISTS cobb_ga_filing;

CREATE TABLE cobb_ga_filing (
    case_number VARCHAR(255) PRIMARY KEY,
    document_type VARCHAR(255),
    filing_date DATE,
    debtor_name TEXT,
    claimant_name TEXT,
    county VARCHAR(255) DEFAULT 'Cobb GA',
    book_page VARCHAR(255) DEFAULT '',
    document_link TEXT DEFAULT '',
    state VARCHAR(10) DEFAULT 'GA',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_new BOOLEAN DEFAULT TRUE,
    "userId" VARCHAR(255) NOT NULL,
    "user" VARCHAR(255) DEFAULT 'user'
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_cobb_ga_filing_user_id ON cobb_ga_filing("userId");
CREATE INDEX IF NOT EXISTS idx_cobb_ga_filing_filing_date ON cobb_ga_filing(filing_date);
CREATE INDEX IF NOT EXISTS idx_cobb_ga_filing_case_number ON cobb_ga_filing(case_number);

-- Grant permissions if needed (adjust as per your database setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON cobb_ga_filing TO your_app_user; 