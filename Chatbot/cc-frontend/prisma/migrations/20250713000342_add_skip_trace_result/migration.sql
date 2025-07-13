-- CreateTable
CREATE TABLE "skip_trace_result" (
    "id" TEXT NOT NULL,
    "raw_address" TEXT NOT NULL,
    "canonical_address" TEXT NOT NULL,
    "address_hash" TEXT NOT NULL,
    "attomid" TEXT,
    "est_balance" DECIMAL(12,2),
    "available_equity" DECIMAL(12,2),
    "ltv" DECIMAL(5,4),
    "market_value" DECIMAL(12,2),
    "loans_count" INTEGER DEFAULT 0,
    "owner_name" TEXT,
    "primary_email" TEXT,
    "primary_phone" TEXT,
    "processed_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "userId" TEXT NOT NULL,

    CONSTRAINT "skip_trace_result_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "skip_trace_result_address_hash_key" ON "skip_trace_result"("address_hash");

-- CreateIndex
CREATE INDEX "skip_trace_result_userId_idx" ON "skip_trace_result"("userId");

-- CreateIndex
CREATE INDEX "skip_trace_result_address_hash_idx" ON "skip_trace_result"("address_hash");

-- CreateIndex
CREATE INDEX "skip_trace_result_canonical_address_idx" ON "skip_trace_result"("canonical_address");

-- AddForeignKey
ALTER TABLE "skip_trace_result" ADD CONSTRAINT "skip_trace_result_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
