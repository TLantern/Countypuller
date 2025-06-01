/*
  Warnings:

  - Added the required column `userId` to the `scraping_job` table without a default value. This is not possible if the table is not empty.

*/
-- AlterTable
ALTER TABLE "scraping_job" ADD COLUMN     "userId" TEXT NOT NULL;

-- AddForeignKey
ALTER TABLE "scraping_job" ADD CONSTRAINT "scraping_job_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
