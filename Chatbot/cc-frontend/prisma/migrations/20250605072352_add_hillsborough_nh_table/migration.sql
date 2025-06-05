-- AlterTable
ALTER TABLE "User" ADD COLUMN     "userType" TEXT NOT NULL DEFAULT 'LPH';

-- CreateTable
CREATE TABLE "md_case_search_filing" (
    "case_number" TEXT NOT NULL,
    "case_url" TEXT,
    "file_date" TIMESTAMP(3),
    "party_name" TEXT,
    "case_type" TEXT,
    "county" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "is_new" BOOLEAN NOT NULL DEFAULT true,
    "doc_type" TEXT,
    "userId" TEXT NOT NULL,
    "property_address" TEXT,
    "defendant_info" TEXT,
    "case_details_raw" TEXT,
    "case_details_scraped_at" TIMESTAMP(3),

    CONSTRAINT "md_case_search_filing_pkey" PRIMARY KEY ("case_number")
);

-- CreateTable
CREATE TABLE "hillsborough_nh_filing" (
    "id" TEXT NOT NULL,
    "document_number" TEXT NOT NULL,
    "document_url" TEXT,
    "recorded_date" TIMESTAMP(3),
    "instrument_type" TEXT,
    "grantor" TEXT,
    "grantee" TEXT,
    "property_address" TEXT,
    "book_page" TEXT,
    "consideration" TEXT,
    "legal_description" TEXT,
    "county" TEXT NOT NULL DEFAULT 'Hillsborough NH',
    "state" TEXT NOT NULL DEFAULT 'NH',
    "filing_date" TEXT,
    "amount" TEXT,
    "parties" TEXT,
    "location" TEXT,
    "status" TEXT NOT NULL DEFAULT 'active',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "is_new" BOOLEAN NOT NULL DEFAULT true,
    "doc_type" TEXT NOT NULL DEFAULT 'lien',
    "userId" TEXT NOT NULL,

    CONSTRAINT "hillsborough_nh_filing_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "md_case_search_filing_userId_idx" ON "md_case_search_filing"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "hillsborough_nh_filing_document_number_key" ON "hillsborough_nh_filing"("document_number");

-- CreateIndex
CREATE INDEX "hillsborough_nh_filing_userId_idx" ON "hillsborough_nh_filing"("userId");

-- CreateIndex
CREATE INDEX "hillsborough_nh_filing_document_number_idx" ON "hillsborough_nh_filing"("document_number");

-- AddForeignKey
ALTER TABLE "md_case_search_filing" ADD CONSTRAINT "md_case_search_filing_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "hillsborough_nh_filing" ADD CONSTRAINT "hillsborough_nh_filing_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
