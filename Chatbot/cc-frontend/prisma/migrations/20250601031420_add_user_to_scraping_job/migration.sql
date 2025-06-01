/*
  Warnings:

  - Added the required column `userId` to the `lis_pendens_filing` table without a default value. This is not possible if the table is not empty.

*/
-- AlterTable
ALTER TABLE "lis_pendens_filing" ADD COLUMN     "userId" TEXT NOT NULL;

-- AddForeignKey
ALTER TABLE "lis_pendens_filing" ADD CONSTRAINT "lis_pendens_filing_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
