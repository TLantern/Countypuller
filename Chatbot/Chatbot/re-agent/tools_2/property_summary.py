"""
Property Summary Generator Tool

This tool uses GPT-4 to generate comprehensive property summaries
when new parcel IDs are encountered in the system.
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
import os
import openai
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to load from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, use environment variables directly
    pass

# Configure OpenAI client
openai.api_key = os.getenv('OPENAI_API_KEY')

class PropertySummaryGenerator:
    """Generates property summaries using GPT-4"""
    
    def __init__(self):
        self.model = "gpt-4"
        self.summaries_cache_file = Path(__file__).parent / "property_summaries_cache.json"
        self.processed_parcels = self._load_processed_parcels()
        
    def _load_processed_parcels(self) -> Dict[str, Dict]:
        """Load previously processed parcel summaries from cache"""
        if self.summaries_cache_file.exists():
            try:
                with open(self.summaries_cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load summaries cache: {e}")
        return {}
    
    def _save_processed_parcels(self):
        """Save processed parcel summaries to cache"""
        try:
            with open(self.summaries_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.processed_parcels, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Could not save summaries cache: {e}")
    
    def is_new_parcel(self, parcel_id: str) -> bool:
        """Check if this is a new parcel ID we haven't processed"""
        return parcel_id not in self.processed_parcels
    
    async def generate_summary(self, property_data: Dict[str, Any], custom_prompt: str = None) -> Dict[str, Any]:
        """
        Generate a property summary using GPT-4
        
        Args:
            property_data: Dictionary containing property information
            custom_prompt: Optional custom prompt for summary generation
            
        Returns:
            Dictionary containing the generated summary and metadata
        """
        parcel_id = property_data.get('parcel_id')
        if not parcel_id:
            return {'error': 'No parcel ID provided'}
        
        # Check if we've already processed this parcel
        if not self.is_new_parcel(parcel_id):
            logger.info(f"📋 Parcel {parcel_id} already processed, returning cached summary")
            return self.processed_parcels[parcel_id]
        
        logger.info(f"🤖 Generating new property summary for parcel {parcel_id}")
        
        # Default prompt if none provided
        if not custom_prompt:
            custom_prompt = self._get_default_prompt()
        
        try:
            # Prepare the property data for the prompt
            property_context = self._format_property_data(property_data)
            
            # Create the full prompt
            full_prompt = f"{custom_prompt}\n\nProperty Data:\n{property_context}"
            
            # Call GPT-4
            response = await self._call_gpt4(full_prompt)
            
            # Create summary result
            summary_result = {
                'parcel_id': parcel_id,
                'summary': response,
                'generated_at': datetime.now().isoformat(),
                'model_used': self.model,
                'property_data': property_data
            }
            
            # Cache the result
            self.processed_parcels[parcel_id] = summary_result
            self._save_processed_parcels()
            
            logger.info(f"✅ Generated summary for parcel {parcel_id}")
            return summary_result
            
        except Exception as e:
            error_result = {
                'parcel_id': parcel_id,
                'error': str(e),
                'generated_at': datetime.now().isoformat()
            }
            logger.error(f"❌ Failed to generate summary for parcel {parcel_id}: {e}")
            return error_result
    
    async def _call_gpt4(self, prompt: str) -> str:
        """Make async call to GPT-4 API"""
        try:
            # Get API key from environment or use fallback
            api_key = os.getenv('OPENAI_API_KEY') or "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"
            
            # Use the newer OpenAI client
            client = openai.AsyncOpenAI(api_key=api_key)
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a real-estate underwriter writing one-liners."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"GPT-4 API call failed: {e}")
            raise
    
    def _format_property_data(self, property_data: Dict[str, Any]) -> str:
        """Format property data for inclusion in the prompt"""
        formatted_lines = []
        
        # Core property information
        if property_data.get('address'):
            formatted_lines.append(f"Address: {property_data['address']}")
        
        if property_data.get('parcel_id'):
            formatted_lines.append(f"Parcel ID: {property_data['parcel_id']}")
        
        if property_data.get('owner_name'):
            formatted_lines.append(f"Owner: {property_data['owner_name']}")
        
        # Property details
        if property_data.get('impr_sqft'):
            formatted_lines.append(f"Improvement Square Feet: {property_data['impr_sqft']}")
        
        if property_data.get('market_value'):
            formatted_lines.append(f"Market Value: {property_data['market_value']}")
        
        if property_data.get('appraised_value'):
            formatted_lines.append(f"Appraised Value: {property_data['appraised_value']}")
        
        # Legal description information
        legal_params = property_data.get('legal_params', {})
        if legal_params.get('subdivision'):
            formatted_lines.append(f"Subdivision: {legal_params['subdivision']}")
        
        if legal_params.get('block'):
            formatted_lines.append(f"Block: {legal_params['block']}")
        
        if legal_params.get('lot'):
            formatted_lines.append(f"Lot: {legal_params['lot']}")
        
        if legal_params.get('section'):
            formatted_lines.append(f"Section: {legal_params['section']}")
        
        return '\n'.join(formatted_lines)
    
    def _get_default_prompt(self) -> str:
        """Default prompt for property summary generation"""
        return """
Please generate a comprehensive property summary based on the provided property data. 
The summary should include:

1. Property Overview (location, type, key characteristics)
2. Financial Analysis (market value, appraised value, value per square foot if applicable)
3. Legal Description Summary (subdivision, block, lot details)
4. Investment Insights (potential risks, opportunities, market position)
5. Notable Features (if any special characteristics can be inferred)

Keep the summary professional, concise (under 500 words), and focused on actionable insights for real estate professionals.
"""

# Main async function for the tool
async def generate_property_summary(property_data: Dict[str, Any], custom_prompt: str = None) -> Dict[str, Any]:
    """
    Generate a property summary using GPT-4
    
    Args:
        property_data: Dictionary containing property information including:
            - address: Property address
            - parcel_id: Unique parcel identifier
            - owner_name: Property owner name
            - impr_sqft: Improvement square footage
            - market_value: Market value
            - appraised_value: Appraised value
            - legal_params: Legal description details
        custom_prompt: Optional custom prompt for summary generation
        
    Returns:
        Dictionary containing:
            - parcel_id: Parcel ID
            - summary: Generated summary text
            - generated_at: Timestamp
            - model_used: GPT model used
            - error: Error message if failed
    """
    generator = PropertySummaryGenerator()
    return await generator.generate_summary(property_data, custom_prompt)

# Batch processing function
async def process_property_batch(properties_list: list, custom_prompt: str = None) -> list:
    """
    Process multiple properties and generate summaries for new parcel IDs
    
    Args:
        properties_list: List of property data dictionaries
        custom_prompt: Optional custom prompt for all summaries
        
    Returns:
        List of summary results
    """
    generator = PropertySummaryGenerator()
    results = []
    
    logger.info(f"🔄 Processing batch of {len(properties_list)} properties")
    
    for i, property_data in enumerate(properties_list, 1):
        parcel_id = property_data.get('parcel_id', 'unknown')
        
        if generator.is_new_parcel(parcel_id):
            logger.info(f"🆕 Processing new parcel {i}/{len(properties_list)}: {parcel_id}")
            result = await generator.generate_summary(property_data, custom_prompt)
            results.append(result)
        else:
            logger.info(f"⏭️ Skipping existing parcel {i}/{len(properties_list)}: {parcel_id}")
            results.append(generator.processed_parcels[parcel_id])
    
    logger.info(f"✅ Completed batch processing: {len(results)} summaries")
    return results

if __name__ == "__main__":
    # Test the property summary generator
    async def test():
        # Sample property data
        test_property = {
            "address": "18414 WATER SCENE, CYPRESS, 77429",
            "parcel_id": "1248470010035",
            "owner_name": "ITANI TARIQ ZIAD",
            "impr_sqft": "7009",
            "market_value": "$317,745",
            "appraised_value": "$317,745",
            "legal_params": {
                "subdivision": "VILLAGES OF CYPRESS LAKES",
                "section": "6",
                "block": "1",
                "lot": "35"
            }
        }
        
        print("Testing Property Summary Generator...")
        result = await generate_property_summary(test_property)
        print(f"Result: {json.dumps(result, indent=2)}")
    
    asyncio.run(test()) 