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

    CONSTRAINT "scraping_job_pkey" PRIMARY KEY ("id")
);
