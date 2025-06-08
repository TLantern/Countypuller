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
    "userId" TEXT NOT NULL,

    CONSTRAINT "lis_pendens_filing_pkey" PRIMARY KEY ("case_number")
);

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

-- CreateTable
CREATE TABLE "brevard_fl_filing" (
    "id" TEXT NOT NULL,
    "case_number" TEXT NOT NULL,
    "document_url" TEXT,
    "file_date" TIMESTAMP(3),
    "case_type" TEXT,
    "party_name" TEXT,
    "property_address" TEXT,
    "county" TEXT NOT NULL DEFAULT 'Brevard',
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "is_new" BOOLEAN NOT NULL DEFAULT true,
    "userId" TEXT NOT NULL,

    CONSTRAINT "brevard_fl_filing_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "firstName" TEXT NOT NULL,
    "password" TEXT NOT NULL,
    "userType" TEXT NOT NULL DEFAULT 'LPH',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "scraping_job" (
    "id" TEXT NOT NULL,
    "job_type" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completed_at" TIMESTAMP(3),
    "parameters" JSONB,
    "result" JSONB,
    "error_message" TEXT,
    "records_processed" INTEGER,
    "userId" TEXT NOT NULL,

    CONSTRAINT "scraping_job_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "accounts" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "provider_account_id" TEXT NOT NULL,
    "refresh_token" TEXT,
    "access_token" TEXT,
    "expires_at" INTEGER,
    "token_type" TEXT,
    "scope" TEXT,
    "id_token" TEXT,
    "session_state" TEXT,

    CONSTRAINT "accounts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sessions" (
    "id" TEXT NOT NULL,
    "session_token" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "expires" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "verificationtokens" (
    "identifier" TEXT NOT NULL,
    "token" TEXT NOT NULL,
    "expires" TIMESTAMP(3) NOT NULL
);

-- CreateIndex
CREATE INDEX "lis_pendens_filing_userId_idx" ON "lis_pendens_filing"("userId");

-- CreateIndex
CREATE INDEX "md_case_search_filing_userId_idx" ON "md_case_search_filing"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "hillsborough_nh_filing_document_number_key" ON "hillsborough_nh_filing"("document_number");

-- CreateIndex
CREATE INDEX "hillsborough_nh_filing_userId_idx" ON "hillsborough_nh_filing"("userId");

-- CreateIndex
CREATE INDEX "hillsborough_nh_filing_document_number_idx" ON "hillsborough_nh_filing"("document_number");

-- CreateIndex
CREATE UNIQUE INDEX "brevard_fl_filing_case_number_key" ON "brevard_fl_filing"("case_number");

-- CreateIndex
CREATE INDEX "brevard_fl_filing_userId_idx" ON "brevard_fl_filing"("userId");

-- CreateIndex
CREATE INDEX "brevard_fl_filing_case_number_idx" ON "brevard_fl_filing"("case_number");

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "User"("email");

-- CreateIndex
CREATE INDEX "scraping_job_userId_idx" ON "scraping_job"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "accounts_provider_provider_account_id_key" ON "accounts"("provider", "provider_account_id");

-- CreateIndex
CREATE UNIQUE INDEX "sessions_session_token_key" ON "sessions"("session_token");

-- CreateIndex
CREATE UNIQUE INDEX "verificationtokens_token_key" ON "verificationtokens"("token");

-- CreateIndex
CREATE UNIQUE INDEX "verificationtokens_identifier_token_key" ON "verificationtokens"("identifier", "token");

-- AddForeignKey
ALTER TABLE "lis_pendens_filing" ADD CONSTRAINT "lis_pendens_filing_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "md_case_search_filing" ADD CONSTRAINT "md_case_search_filing_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "hillsborough_nh_filing" ADD CONSTRAINT "hillsborough_nh_filing_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "brevard_fl_filing" ADD CONSTRAINT "brevard_fl_filing_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "scraping_job" ADD CONSTRAINT "scraping_job_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "accounts" ADD CONSTRAINT "accounts_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;
