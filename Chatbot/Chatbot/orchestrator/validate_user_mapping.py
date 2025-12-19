#!/usr/bin/env python3
"""
User ID Validation Script for Harris County Records

This script validates that Harris County records are being saved with the correct user ID
and provides utilities to fix any mismatches.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def validate_user_mapping(user_id: str) -> Dict[str, Any]:
    """
    Validate that Harris County records are correctly mapped to the user
    
    Args:
        user_id: The expected user ID for recent records
        
    Returns:
        Dict with validation results
    """
    try:
        import asyncpg
        
        # Get database URL
        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL not found in environment")
        
        if DATABASE_URL.startswith("postgresql://"):
            DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgres://")
        
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Check recent Harris County records (last 24 hours)
        recent_cutoff = datetime.now() - timedelta(hours=24)
        
        recent_records = await conn.fetch("""
            SELECT case_number, "userId", created_at
            FROM harris_county_filing
            WHERE created_at >= $1
            ORDER BY created_at DESC
        """, recent_cutoff)
        
        # Check recent scraping jobs
        recent_jobs = await conn.fetch("""
            SELECT id, "userId", created_at, status
            FROM scraping_job
            WHERE job_type = 'AGENT_SCRAPE' AND created_at >= $1
            ORDER BY created_at DESC
        """, recent_cutoff)
        
        await conn.close()
        
        # Analyze results
        total_records = len(recent_records)
        correct_user_records = sum(1 for r in recent_records if r['userId'] == user_id)
        mismatched_records = total_records - correct_user_records
        
        # Find unique user IDs in records
        record_user_ids = set(r['userId'] for r in recent_records)
        job_user_ids = set(j['userId'] for j in recent_jobs)
        
        result = {
            'validation_time': datetime.now().isoformat(),
            'expected_user_id': user_id,
            'total_recent_records': total_records,
            'correct_user_records': correct_user_records,
            'mismatched_records': mismatched_records,
            'record_user_ids': list(record_user_ids),
            'job_user_ids': list(job_user_ids),
            'is_valid': mismatched_records == 0,
            'recent_records': [
                {
                    'case_number': r['case_number'],
                    'userId': r['userId'],
                    'created_at': r['created_at'].isoformat(),
                    'is_correct': r['userId'] == user_id
                }
                for r in recent_records[:10]  # Show first 10
            ],
            'recent_jobs': [
                {
                    'id': j['id'],
                    'userId': j['userId'],
                    'created_at': j['created_at'].isoformat(),
                    'status': j['status']
                }
                for j in recent_jobs[:5]  # Show first 5
            ]
        }
        
        if result['is_valid']:
            logger.info(f"✅ User mapping validation PASSED - all {total_records} records correctly mapped to {user_id}")
        else:
            logger.warning(f"❌ User mapping validation FAILED - {mismatched_records} out of {total_records} records have incorrect user ID")
            logger.warning(f"Expected: {user_id}")
            logger.warning(f"Found user IDs in records: {record_user_ids}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Validation failed: {e}")
        return {
            'validation_time': datetime.now().isoformat(),
            'error': str(e),
            'is_valid': False
        }

async def fix_user_mapping(expected_user_id: str, dry_run: bool = True) -> Dict[str, Any]:
    """
    Fix user ID mapping for recent Harris County records
    
    Args:
        expected_user_id: The correct user ID
        dry_run: If True, only show what would be changed
        
    Returns:
        Dict with fix results
    """
    try:
        import asyncpg
        
        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL not found in environment")
        
        if DATABASE_URL.startswith("postgresql://"):
            DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgres://")
        
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Find records with incorrect user ID (last 24 hours)
        recent_cutoff = datetime.now() - timedelta(hours=24)
        
        incorrect_records = await conn.fetch("""
            SELECT case_number, "userId", created_at
            FROM harris_county_filing
            WHERE created_at >= $1 AND "userId" != $2
            ORDER BY created_at DESC
        """, recent_cutoff, expected_user_id)
        
        result = {
            'fix_time': datetime.now().isoformat(),
            'expected_user_id': expected_user_id,
            'dry_run': dry_run,
            'records_to_fix': len(incorrect_records),
            'records': [
                {
                    'case_number': r['case_number'],
                    'current_userId': r['userId'],
                    'created_at': r['created_at'].isoformat()
                }
                for r in incorrect_records
            ]
        }
        
        if not dry_run and incorrect_records:
            # Actually fix the records
            update_result = await conn.execute("""
                UPDATE harris_county_filing
                SET "userId" = $1, updated_at = NOW()
                WHERE created_at >= $2 AND "userId" != $1
            """, expected_user_id, recent_cutoff)
            
            # Parse the update result (format: "UPDATE n")
            updated_count = int(update_result.split()[-1])
            result['records_updated'] = updated_count
            
            logger.info(f"✅ Fixed {updated_count} records to use correct user ID: {expected_user_id}")
        else:
            result['records_updated'] = 0
            if incorrect_records:
                logger.info(f"🔍 DRY RUN: Would fix {len(incorrect_records)} records")
            else:
                logger.info("✅ No records need fixing")
        
        await conn.close()
        return result
        
    except Exception as e:
        logger.error(f"❌ Fix failed: {e}")
        return {
            'fix_time': datetime.now().isoformat(),
            'error': str(e),
            'records_updated': 0
        }

async def main():
    """CLI interface for user mapping validation and fixing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate and fix Harris County user ID mapping')
    parser.add_argument('--user-id', required=True, help='Expected user ID')
    parser.add_argument('--fix', action='store_true', help='Fix incorrect mappings')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Show what would be fixed without changing anything')
    
    args = parser.parse_args()
    
    # If --fix is specified without --dry-run, actually perform the fix
    if args.fix and not args.dry_run:
        args.dry_run = False
    
    try:
        # Validate current state
        validation_result = await validate_user_mapping(args.user_id)
        
        print("=== VALIDATION RESULTS ===")
        print(f"Expected User ID: {validation_result.get('expected_user_id', 'N/A')}")
        print(f"Total Recent Records: {validation_result.get('total_recent_records', 0)}")
        print(f"Correct User Records: {validation_result.get('correct_user_records', 0)}")
        print(f"Mismatched Records: {validation_result.get('mismatched_records', 0)}")
        print(f"Validation Status: {'✅ PASSED' if validation_result.get('is_valid', False) else '❌ FAILED'}")
        
        # If validation failed and fix is requested
        if not validation_result.get('is_valid', False) and args.fix:
            print("\n=== FIXING USER MAPPING ===")
            fix_result = await fix_user_mapping(args.user_id, args.dry_run)
            
            print(f"Records to Fix: {fix_result.get('records_to_fix', 0)}")
            print(f"Records Updated: {fix_result.get('records_updated', 0)}")
            print(f"Mode: {'DRY RUN' if fix_result.get('dry_run', True) else 'LIVE FIX'}")
        
        return 0 if validation_result.get('is_valid', False) else 1
        
    except Exception as e:
        logger.error(f"❌ Script failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 