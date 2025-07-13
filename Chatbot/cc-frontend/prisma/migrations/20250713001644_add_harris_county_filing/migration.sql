-- CreateTable
CREATE TABLE "harris_county_filing" (
    "case_number" TEXT NOT NULL,
    "filing_date" TIMESTAMP(3),
    "doc_type" TEXT,
    "subdivision" TEXT,
    "section" TEXT,
    "block" TEXT,
    "lot" TEXT,
    "property_address" TEXT,
    "parcel_id" TEXT,
    "ai_summary" TEXT,
    "county" TEXT DEFAULT 'Harris',
    "state" TEXT DEFAULT 'TX',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "is_new" BOOLEAN NOT NULL DEFAULT true,
    "userId" TEXT NOT NULL,

    CONSTRAINT "harris_county_filing_pkey" PRIMARY KEY ("case_number")
);

-- CreateIndex
CREATE INDEX "harris_county_filing_userId_idx" ON "harris_county_filing"("userId");

-- AddForeignKey
ALTER TABLE "harris_county_filing" ADD CONSTRAINT "harris_county_filing_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
