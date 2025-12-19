#!/usr/bin/env python3
"""
Command Line Interface for LisPendens Agent System

This script provides a CLI interface for the agent system to be used by the job worker.
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime
from agent_core import LisPendensAgent, AgentScrapeParams

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    parser = argparse.ArgumentParser(description='LisPendens Agent CLI')
    parser.add_argument('--county', default='harris', help='County to scrape (default: harris)')
    parser.add_argument('--user-id', required=True, help='User ID for the scraping job')
    parser.add_argument('--date-from', help='Start date in YYYY-MM-DD format')
    parser.add_argument('--date-to', help='End date in YYYY-MM-DD format')
    parser.add_argument('--document-type', default='LisPendens', help='Document type to scrape (default: LisPendens)')
    parser.add_argument('--page-size', type=int, default=50, help='Number of records per page (default: 50)')
    parser.add_argument('--target-count', type=int, default=10, help='Target number of valid records to return (default: 10)')
    
    args = parser.parse_args()
    
    try:
        logger.info(f"🚀 Starting agent scrape for {args.county} county")
        logger.info(f"👤 User ID: {args.user_id}")
        logger.info(f"🎯 Target count: {args.target_count} valid records")
        
        # Create agent instance
        agent = LisPendensAgent()
        
        # Prepare filters
        filters = {
            'document_type': args.document_type,
            'page_size': args.page_size,
            'target_count': args.target_count
        }
        
        if args.date_from:
            filters['date_from'] = args.date_from
        if args.date_to:
            filters['date_to'] = args.date_to
        
        # Set up parameters
        params = AgentScrapeParams(
            county=args.county,
            filters=filters,
            user_id=args.user_id
        )
        
        # Run the agent
        result = await agent.scrape(params)
        
        # Output results as JSON
        print(json.dumps(result, indent=2, default=str))
        
        logger.info(f"✅ Agent scrape completed successfully")
        logger.info(f"📊 Total found: {result['metadata']['total_found']}")
        logger.info(f"📊 Processed: {result['metadata']['processed']}")
        logger.info(f"📊 Final records: {len(result['records'])}")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Agent scrape failed: {e}")
        print(json.dumps({
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }, indent=2))
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 