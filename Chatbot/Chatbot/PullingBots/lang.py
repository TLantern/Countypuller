"""
LangChain ChatGPT Agent for County Site Scraping
==================================================

This module provides an intelligent agent that can orchestrate county site scraping
using a modular scraper factory. The agent can:

1. Analyze county websites and determine scraper configuration
2. Generate appropriate scraper configs
3. Execute scraping tasks with intelligent error handling
4. Optimize scraping strategies based on site behavior

The agent integrates with the modular scraper factory to provide a unified
interface for scraping any county website.
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from pathlib import Path

# LangChain imports
from langchain.agents import initialize_agent, AgentType
from langchain.tools import BaseTool, tool
from langchain.schema import BaseMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.memory import ConversationBufferMemory
from langchain.callbacks.base import BaseCallbackHandler

# Pydantic for structured outputs
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

# Local imports
from scraper_factory import ScraperFactory, ScraperType
from config_schemas import CountyConfig, SiteAnalysis

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# PYDANTIC MODELS FOR STRUCTURED OUTPUT
# ─────────────────────────────────────────────────────────────────────────────

class ScrapingTask(BaseModel):
    """Represents a scraping task with all necessary parameters"""
    county_name: str = Field(description="Name of the county")
    base_url: str = Field(description="Base URL of the county website")
    scraper_type: str = Field(description="Type of scraper needed (static_html, search_form, authenticated)")
    search_terms: List[str] = Field(default=[], description="Search terms to use")
    date_range: Optional[Dict[str, str]] = Field(default=None, description="Date range for search")
    max_records: int = Field(default=100, description="Maximum records to scrape")
    
class ConfigGenerationResponse(BaseModel):
    """Response from config generation"""
    success: bool
    config: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    suggestions: List[str] = Field(default=[], description="Suggestions for improvement")

class ScrapingResult(BaseModel):
    """Result from a scraping operation"""
    success: bool
    records_found: int = 0
    records_saved: int = 0
    error_message: Optional[str] = None
    execution_time: float = 0.0
    next_steps: List[str] = Field(default=[], description="Suggested next steps")

# ─────────────────────────────────────────────────────────────────────────────
# LANGCHAIN TOOLS
# ─────────────────────────────────────────────────────────────────────────────

class SiteAnalysisTool(BaseTool):
    """Tool for analyzing county websites to determine scraper configuration"""
    name = "analyze_county_site"
    description = "Analyze a county website to determine the best scraping approach and generate configuration"
    
    def _run(self, url: str, county_name: str) -> str:
        """Analyze the site synchronously"""
        return asyncio.run(self._arun(url, county_name))
    
    async def _arun(self, url: str, county_name: str) -> str:
        """Analyze the site and return structured analysis"""
        factory = ScraperFactory()
        analysis = await factory.analyze_site(url)
        
        return json.dumps({
            "county_name": county_name,
            "url": url,
            "scraper_type": analysis.scraper_type.value,
            "complexity": analysis.complexity,
            "required_fields": analysis.required_fields,
            "authentication_required": analysis.authentication_required,
            "captcha_present": analysis.captcha_present,
            "pagination_type": analysis.pagination_type,
            "suggested_selectors": analysis.suggested_selectors
        }, indent=2)

class ConfigGeneratorTool(BaseTool):
    """Tool for generating scraper configurations"""
    name = "generate_scraper_config"
    description = "Generate a scraper configuration file based on site analysis"
    
    def _run(self, analysis_json: str, county_name: str) -> str:
        """Generate config synchronously"""
        return asyncio.run(self._arun(analysis_json, county_name))
    
    async def _arun(self, analysis_json: str, county_name: str) -> str:
        """Generate scraper configuration"""
        try:
            analysis_data = json.loads(analysis_json)
            factory = ScraperFactory()
            
            config = await factory.generate_config(
                county_name=county_name,
                analysis=SiteAnalysis(**analysis_data)
            )
            
            return json.dumps({
                "success": True,
                "config": config.dict(),
                "suggestions": [
                    "Test the configuration with a small date range first",
                    "Monitor for rate limiting or blocking",
                    "Verify selector accuracy with manual testing"
                ]
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error_message": str(e),
                "suggestions": [
                    "Check the site analysis data format",
                    "Verify the county website is accessible",
                    "Try manual analysis of the site structure"
                ]
            }, indent=2)

class ScraperExecutorTool(BaseTool):
    """Tool for executing scraping tasks"""
    name = "execute_scraping"
    description = "Execute a scraping task using the generated configuration"
    
    def _run(self, config_json: str, task_params: str) -> str:
        """Execute scraping synchronously"""
        return asyncio.run(self._arun(config_json, task_params))
    
    async def _arun(self, config_json: str, task_params: str) -> str:
        """Execute the scraping task"""
        try:
            config_data = json.loads(config_json)
            task_data = json.loads(task_params)
            
            factory = ScraperFactory()
            config = CountyConfig(**config_data)
            
            start_time = datetime.now()
            result = await factory.execute_scraping(config, task_data)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return json.dumps({
                "success": result.success,
                "records_found": len(result.records) if result.records else 0,
                "records_saved": result.records_saved,
                "execution_time": execution_time,
                "error_message": result.error_message,
                "next_steps": [
                    "Review scraped data for accuracy",
                    "Set up automated scheduling if successful",
                    "Monitor for changes in website structure"
                ]
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error_message": str(e),
                "next_steps": [
                    "Check configuration format",
                    "Verify website accessibility",
                    "Review error logs for details"
                ]
            }, indent=2)

# ─────────────────────────────────────────────────────────────────────────────
# LANGCHAIN AGENT
# ─────────────────────────────────────────────────────────────────────────────

class CountyScrapingAgent:
    """LangChain agent for intelligent county website scraping"""
    
    def __init__(self, openai_api_key: str = None):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required")
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            temperature=0.1,
            model="gpt-4-turbo-preview",
            openai_api_key=self.openai_api_key
        )
        
        # Initialize tools
        self.tools = [
            SiteAnalysisTool(),
            ConfigGeneratorTool(),
            ScraperExecutorTool(),
            DuckDuckGoSearchRun()
        ]
        
        # Initialize memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Initialize agent
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True
        )
        
        # System prompt
        self.system_prompt = """
        You are an expert web scraper and data extraction specialist. Your job is to help users 
        scrape county websites efficiently and ethically. You have access to a modular scraper 
        factory that can handle different types of county websites.
        
        Your capabilities include:
        1. Analyzing county websites to determine the best scraping approach
        2. Generating appropriate scraper configurations
        3. Executing scraping tasks with error handling
        4. Providing optimization suggestions
        
        Always follow these principles:
        - Respect robots.txt and rate limits
        - Use appropriate delays between requests
        - Handle errors gracefully
        - Provide clear feedback to users
        - Suggest improvements and optimizations
        
        When a user asks you to scrape a county website:
        1. First analyze the site structure
        2. Generate appropriate configuration
        3. Execute the scraping if requested
        4. Provide results and next steps
        """
    
    async def analyze_and_scrape(self, county_name: str, website_url: str, 
                                search_terms: List[str] = None, 
                                date_range: Dict[str, str] = None,
                                max_records: int = 100) -> Dict[str, Any]:
        """
        Complete workflow: analyze site, generate config, and execute scraping
        """
        
        try:
            # Step 1: Analyze the site
            analysis_prompt = f"""
            Please analyze the county website for {county_name} at {website_url}.
            
            I need to scrape recent records like liens, foreclosures, and other legal documents.
            Use the analyze_county_site tool to determine the best scraping approach.
            """
            
            analysis_response = await self.agent.arun(analysis_prompt)
            
            # Step 2: Generate configuration
            config_prompt = f"""
            Based on the site analysis, please generate a scraper configuration for {county_name}.
            Use the generate_scraper_config tool with the analysis results.
            """
            
            config_response = await self.agent.arun(config_prompt)
            
            # Step 3: Execute scraping if requested
            if search_terms or date_range:
                task_params = {
                    "search_terms": search_terms or [],
                    "date_range": date_range,
                    "max_records": max_records
                }
                
                execution_prompt = f"""
                Now execute the scraping task using the generated configuration.
                Task parameters: {json.dumps(task_params)}
                Use the execute_scraping tool.
                """
                
                execution_response = await self.agent.arun(execution_prompt)
                
                return {
                    "analysis": analysis_response,
                    "configuration": config_response,
                    "execution": execution_response
                }
            else:
                return {
                    "analysis": analysis_response,
                    "configuration": config_response,
                    "message": "Configuration generated. Provide search parameters to execute scraping."
                }
                
        except Exception as e:
            return {
                "error": str(e),
                "message": "Failed to complete scraping workflow"
            }
    
    async def chat(self, message: str) -> str:
        """
        General chat interface for the scraping agent
        """
        try:
            response = await self.agent.arun(message)
            return response
        except Exception as e:
            return f"Error: {str(e)}"
    
    def optimize_config(self, config: Dict[str, Any], performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use AI to optimize scraper configuration based on performance data
        """
        prompt = f"""
        I have a scraper configuration that needs optimization:
        
        Current Config: {json.dumps(config, indent=2)}
        Performance Data: {json.dumps(performance_data, indent=2)}
        
        Please suggest improvements to:
        1. Increase success rate
        2. Reduce execution time
        3. Handle errors better
        4. Improve data quality
        
        Provide specific recommendations with updated configuration values.
        """
        
        try:
            response = self.agent.run(prompt)
            return {"suggestions": response}
        except Exception as e:
            return {"error": str(e)}

# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

async def quick_scrape(county_name: str, website_url: str, 
                      search_terms: List[str] = None,
                      max_records: int = 50) -> Dict[str, Any]:
    """
    Quick scraping function for simple use cases
    """
    agent = CountyScrapingAgent()
    return await agent.analyze_and_scrape(
        county_name=county_name,
        website_url=website_url,
        search_terms=search_terms,
        max_records=max_records
    )

async def generate_config_only(county_name: str, website_url: str) -> Dict[str, Any]:
    """
    Generate configuration without executing scraping
    """
    agent = CountyScrapingAgent()
    return await agent.analyze_and_scrape(
        county_name=county_name,
        website_url=website_url
    )

# ─────────────────────────────────────────────────────────────────────────────
# CLI INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import click
    
    @click.group()
    def cli():
        """LangChain County Scraping Agent CLI"""
        pass
    
    @cli.command()
    @click.argument('county_name')
    @click.argument('website_url')
    @click.option('--search-terms', multiple=True, help='Search terms to use')
    @click.option('--max-records', default=50, help='Maximum records to scrape')
    async def scrape(county_name, website_url, search_terms, max_records):
        """Analyze and scrape a county website"""
        result = await quick_scrape(
            county_name=county_name,
            website_url=website_url,
            search_terms=list(search_terms) if search_terms else None,
            max_records=max_records
        )
        print(json.dumps(result, indent=2))
    
    @cli.command()
    @click.argument('county_name')
    @click.argument('website_url')
    async def analyze(county_name, website_url):
        """Analyze a county website and generate configuration"""
        result = await generate_config_only(county_name, website_url)
        print(json.dumps(result, indent=2))
    
    @cli.command()
    async def chat():
        """Start interactive chat with the scraping agent"""
        agent = CountyScrapingAgent()
        print("County Scraping Agent - Type 'quit' to exit")
        
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ['quit', 'exit']:
                break
            
            response = await agent.chat(user_input)
            print(f"\nAgent: {response}")
    
    cli()