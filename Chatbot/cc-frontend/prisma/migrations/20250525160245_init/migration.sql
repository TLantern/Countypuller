-- CreateTable
CREATE TABLE "lis_pendens_filing" (
    "case_number" TEXT NOT NULL,
    "case_url" TEXT,
    "file_date" TIMESTAMP(3) NOT NULL,
    "property_address" TEXT NOT NULL,
    "filing_no" TEXT,
    "volume_no" TEXT,
    "page_no" TEXT,
    "county" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "is_new" BOOLEAN NOT NULL DEFAULT true,
    "doc_type" TEXT NOT NULL,

    CONSTRAINT "lis_pendens_filing_pkey" PRIMARY KEY ("case_number")
);
