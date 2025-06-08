#!/usr/bin/env python3
"""
Scraper Generator CLI
====================

Command-line interface for the modular county scraper factory.
Generates running scrapers from configuration files in under 5 minutes.

Usage:
    python scraper_cli.py analyze <url> --county "County Name"
    python scraper_cli.py generate <config_file> --output <scraper_file>
    python scraper_cli.py run <config_file> --max-records 100
    python scraper_cli.py chat
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.json import JSON

# Local imports
from scraper_factory import ScraperFactory, quick_analyze, generate_config_from_url
from config_schemas import CountyConfig, ScraperType, get_static_html_template, get_search_form_template, get_authenticated_template
from lang import CountyScrapingAgent, quick_scrape, generate_config_only

console = Console()

# ─────────────────────────────────────────────────────────────────────────────
# CLI COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

@click.group()
@click.version_option(version="1.0.0")
def cli():
    """
    🔍 Modular County Scraper Factory CLI
    
    Generate and run county website scrapers in minutes!
    """
    pass

@cli.command()
@click.argument('url')
@click.option('--county', required=True, help='County name')
@click.option('--output', help='Output configuration file')
@click.option('--save-analysis', is_flag=True, help='Save analysis results')
async def analyze(url: str, county: str, output: Optional[str], save_analysis: bool):
    """
    🔍 Analyze a county website and generate configuration
    
    Examines the website structure and recommends the best scraping approach.
    """
    console.print(f"\n[bold blue]🔍 Analyzing {county} website...[/bold blue]")
    console.print(f"URL: {url}")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Analyzing website structure...", total=None)
        
        try:
            # Perform analysis
            factory = ScraperFactory()
            analysis = await factory.analyze_site(url)
            
            progress.update(task, description="Generating configuration...")
            config = await factory.generate_config(county, analysis)
            
            # Display results
            console.print("\n[bold green]✅ Analysis Complete![/bold green]")
            
            # Analysis summary table
            table = Table(title="Site Analysis Summary")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")
            
            table.add_row("Scraper Type", analysis.scraper_type.value)
            table.add_row("Complexity (1-10)", str(analysis.complexity))
            table.add_row("Authentication Required", "Yes" if analysis.authentication_required else "No")
            table.add_row("CAPTCHA Present", "Yes" if analysis.captcha_present else "No")
            table.add_row("Pagination Type", analysis.pagination_type.value)
            table.add_row("JavaScript Heavy", "Yes" if analysis.javascript_heavy else "No")
            table.add_row("Required Fields", ", ".join(analysis.required_fields))
            
            console.print(table)
            
            # Show suggested selectors
            if analysis.suggested_selectors:
                console.print("\n[bold cyan]🎯 Suggested Selectors:[/bold cyan]")
                for field, selector in analysis.suggested_selectors.items():
                    console.print(f"  • {field}: [green]{selector}[/green]")
            
            # Save configuration if requested
            if output:
                config.to_json_file(output)
                console.print(f"\n[bold green]💾 Configuration saved to:[/bold green] {output}")
            else:
                # Auto-generate filename
                filename = f"configs/{county.lower().replace(' ', '_')}.json"
                Path("configs").mkdir(exist_ok=True)
                config.to_json_file(filename)
                console.print(f"\n[bold green]💾 Configuration saved to:[/bold green] {filename}")
            
            # Save analysis if requested
            if save_analysis:
                analysis_file = f"analysis_{county.lower().replace(' ', '_')}.json"
                with open(analysis_file, 'w') as f:
                    json.dump(analysis.dict(), f, indent=2, default=str)
                console.print(f"[bold blue]📊 Analysis saved to:[/bold blue] {analysis_file}")
            
            # Show next steps
            console.print("\n[bold yellow]🚀 Next Steps:[/bold yellow]")
            console.print("1. Review and customize the generated configuration")
            console.print("2. Test with: [green]scraper_cli.py run <config_file> --test[/green]")
            console.print("3. Run full scraping: [green]scraper_cli.py run <config_file>[/green]")
            
        except Exception as e:
            console.print(f"\n[bold red]❌ Analysis failed:[/bold red] {str(e)}")
            sys.exit(1)

@cli.command()
@click.argument('config_file')
@click.option('--output', help='Output Python scraper file')
@click.option('--template', type=click.Choice(['basic', 'advanced', 'class']), default='basic', help='Scraper template type')
def generate(config_file: str, output: Optional[str], template: str):
    """
    🏭 Generate a Python scraper from configuration file
    
    Creates a ready-to-run Python scraper based on the configuration.
    """
    console.print(f"\n[bold blue]🏭 Generating scraper from configuration...[/bold blue]")
    
    try:
        # Load configuration
        config = CountyConfig.from_json_file(config_file)
        
        # Generate output filename if not provided
        if not output:
            output = f"{config.name.lower().replace(' ', '_')}_scraper.py"
        
        # Generate scraper code
        scraper_code = generate_scraper_code(config, template)
        
        # Write to file
        with open(output, 'w') as f:
            f.write(scraper_code)
        
        console.print(f"\n[bold green]✅ Scraper generated successfully![/bold green]")
        console.print(f"File: [cyan]{output}[/cyan]")
        
        # Show usage instructions
        console.print("\n[bold yellow]🚀 Usage:[/bold yellow]")
        console.print(f"python {output} --help")
        console.print(f"python {output} --max-records 50 --test")
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Generation failed:[/bold red] {str(e)}")
        sys.exit(1)

@cli.command()
@click.argument('config_file')
@click.option('--max-records', default=50, help='Maximum records to scrape')
@click.option('--test', is_flag=True, help='Run in test mode')
@click.option('--date-from', help='Start date (YYYY-MM-DD)')
@click.option('--date-to', help='End date (YYYY-MM-DD)')
@click.option('--search-terms', multiple=True, help='Search terms')
@click.option('--headless/--no-headless', default=True, help='Run browser in headless mode')
async def run(config_file: str, max_records: int, test: bool, date_from: Optional[str], 
              date_to: Optional[str], search_terms: tuple, headless: bool):
    """
    🚀 Run scraper with the specified configuration
    
    Executes the scraping task using the provided configuration file.
    """
    console.print(f"\n[bold blue]🚀 Running scraper...[/bold blue]")
    
    try:
        # Load configuration
        config = CountyConfig.from_json_file(config_file)
        config.headless = headless
        
        # Prepare task parameters
        task_params = {
            'max_records': max_records,
            'test_mode': test
        }
        
        if date_from or date_to:
            task_params['date_range'] = {
                'from': date_from or '',
                'to': date_to or ''
            }
        
        if search_terms:
            task_params['search_terms'] = list(search_terms)
        
        console.print(f"County: [cyan]{config.name}[/cyan]")
        console.print(f"Scraper Type: [yellow]{config.scraper_type.value}[/yellow]")
        console.print(f"Max Records: [green]{max_records}[/green]")
        
        if test:
            console.print("[bold yellow]⚠️  Running in TEST MODE[/bold yellow]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Initializing scraper...", total=None)
            
            # Create and run scraper
            factory = ScraperFactory()
            
            progress.update(task, description="Analyzing website...")
            result = await factory.execute_scraping(config, task_params)
            
            progress.update(task, description="Extracting data...")
            
        # Display results
        if result.success:
            console.print(f"\n[bold green]✅ Scraping completed successfully![/bold green]")
            
            results_table = Table(title="Scraping Results")
            results_table.add_column("Metric", style="cyan")
            results_table.add_column("Value", style="white")
            
            results_table.add_row("Records Found", str(len(result.records)))
            results_table.add_row("Records Saved", str(result.records_saved))
            results_table.add_row("Pages Scraped", str(result.total_pages_scraped))
            results_table.add_row("Execution Time", f"{result.execution_time:.2f} seconds")
            
            console.print(results_table)
            
            # Show sample records
            if result.records and len(result.records) > 0:
                console.print("\n[bold cyan]📄 Sample Records:[/bold cyan]")
                for i, record in enumerate(result.records[:3]):
                    console.print(f"\n[bold]Record {i+1}:[/bold]")
                    for key, value in record.data.items():
                        console.print(f"  {key}: [green]{value}[/green]")
        else:
            console.print(f"\n[bold red]❌ Scraping failed:[/bold red] {result.error_message}")
            sys.exit(1)
            
    except Exception as e:
        console.print(f"\n[bold red]❌ Execution failed:[/bold red] {str(e)}")
        sys.exit(1)

@cli.command()
async def chat():
    """
    💬 Interactive chat with the scraping agent
    
    Start a conversation with the AI-powered scraping assistant.
    """
    console.print(Panel(
        "[bold blue]🤖 County Scraping Agent[/bold blue]\n\n"
        "I can help you analyze websites, generate configurations, and run scrapers!\n"
        "Type 'help' for commands or 'quit' to exit.",
        title="AI Assistant"
    ))
    
    try:
        agent = CountyScrapingAgent()
        
        while True:
            user_input = console.input("\n[bold cyan]You:[/bold cyan] ")
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                console.print("\n[bold green]👋 Goodbye![/bold green]")
                break
            
            if user_input.lower() == 'help':
                show_chat_help()
                continue
            
            with Progress(
                SpinnerColumn(),
                TextColumn("AI is thinking..."),
                console=console
            ) as progress:
                progress.add_task("", total=None)
                response = await agent.chat(user_input)
            
            console.print(f"\n[bold yellow]🤖 Agent:[/bold yellow] {response}")
            
    except KeyboardInterrupt:
        console.print("\n\n[bold green]👋 Goodbye![/bold green]")
    except Exception as e:
        console.print(f"\n[bold red]❌ Chat error:[/bold red] {str(e)}")

@cli.command()
@click.option('--type', 'scraper_type', type=click.Choice(['static_html', 'search_form', 'authenticated']), 
              required=True, help='Type of scraper template')
@click.option('--county', required=True, help='County name')
@click.option('--url', required=True, help='Base URL')
@click.option('--output', help='Output configuration file')
def template(scraper_type: str, county: str, url: str, output: Optional[str]):
    """
    📋 Create configuration from template
    
    Generate a basic configuration file from a template.
    """
    console.print(f"\n[bold blue]📋 Creating {scraper_type} template...[/bold blue]")
    
    try:
        factory = ScraperFactory()
        
        # Create config from template
        type_enum = ScraperType(scraper_type)
        config = factory.create_config_from_template(type_enum, county, url)
        
        # Save configuration
        if not output:
            output = f"configs/{county.lower().replace(' ', '_')}.json"
        
        Path("configs").mkdir(exist_ok=True)
        config.to_json_file(output)
        
        console.print(f"\n[bold green]✅ Template created![/bold green]")
        console.print(f"File: [cyan]{output}[/cyan]")
        
        # Show configuration summary
        table = Table(title="Configuration Summary")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("County", config.name)
        table.add_row("Type", config.scraper_type.value)
        table.add_row("URL", config.base_url)
        table.add_row("Fields", str(len(config.field_mappings)))
        
        console.print(table)
        
        console.print("\n[bold yellow]⚠️  Remember to customize the selectors and field mappings![/bold yellow]")
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Template creation failed:[/bold red] {str(e)}")
        sys.exit(1)

@cli.command()
@click.option('--config-dir', default='configs', help='Configuration directory')
def list_configs(config_dir: str):
    """
    📁 List available configuration files
    """
    console.print(f"\n[bold blue]📁 Available Configurations in {config_dir}/[/bold blue]")
    
    config_path = Path(config_dir)
    if not config_path.exists():
        console.print("[bold red]❌ Configuration directory not found![/bold red]")
        return
    
    config_files = list(config_path.glob("*.json"))
    
    if not config_files:
        console.print("[yellow]No configuration files found.[/yellow]")
        return
    
    table = Table()
    table.add_column("Configuration", style="cyan")
    table.add_column("County", style="white")
    table.add_column("Type", style="yellow")
    table.add_column("Last Modified", style="green")
    
    for config_file in config_files:
        try:
            config = CountyConfig.from_json_file(str(config_file))
            modified = time.ctime(config_file.stat().st_mtime)
            table.add_row(
                config_file.name,
                config.name,
                config.scraper_type.value,
                modified
            )
        except Exception as e:
            table.add_row(config_file.name, "ERROR", str(e), "")
    
    console.print(table)

# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def show_chat_help():
    """Show help for chat commands"""
    help_panel = Panel(
        "[bold cyan]Available Commands:[/bold cyan]\n\n"
        "• analyze <url> --county 'Name' - Analyze a county website\n"
        "• scrape <url> --county 'Name' --terms 'foreclosure,lien' - Quick scrape\n"
        "• help - Show this help\n"
        "• quit/exit - Exit chat\n\n"
        "[bold yellow]Example:[/bold yellow]\n"
        "analyze https://example.com/records --county 'Harris County'",
        title="Chat Help"
    )
    console.print(help_panel)

def generate_scraper_code(config: CountyConfig, template: str) -> str:
    """Generate Python scraper code from configuration"""
    
    if template == 'basic':
        return generate_basic_scraper_template(config)
    elif template == 'advanced':
        return generate_advanced_scraper_template(config)
    elif template == 'class':
        return generate_class_scraper_template(config)
    else:
        raise ValueError(f"Unknown template type: {template}")

def generate_basic_scraper_template(config: CountyConfig) -> str:
    """Generate basic scraper template"""
    return f'''#!/usr/bin/env python3
"""
{config.name} Scraper
Generated by Modular County Scraper Factory
"""

import asyncio
import json
from pathlib import Path

from scraper_factory import ScraperFactory
from config_schemas import CountyConfig

async def main():
    """Main scraping function"""
    
    # Load configuration
    config = CountyConfig.from_json_file("{config.name.lower().replace(' ', '_')}.json")
    
    # Set up task parameters
    task_params = {{
        'max_records': 100,
        'date_range': {{
            'from': '2024-01-01',
            'to': '2024-12-31'
        }}
    }}
    
    # Create and run scraper
    factory = ScraperFactory()
    result = await factory.execute_scraping(config, task_params)
    
    if result.success:
        print(f"✅ Successfully scraped {{len(result.records)}} records")
        
        # Save results
        output_file = "results_{config.name.lower().replace(' ', '_')}.json"
        with open(output_file, 'w') as f:
            json.dump([record.data for record in result.records], f, indent=2, default=str)
        
        print(f"📄 Results saved to {{output_file}}")
    else:
        print(f"❌ Scraping failed: {{result.error_message}}")

if __name__ == "__main__":
    asyncio.run(main())
'''

def generate_advanced_scraper_template(config: CountyConfig) -> str:
    """Generate advanced scraper template with CLI options"""
    return f'''#!/usr/bin/env python3
"""
{config.name} Advanced Scraper
Generated by Modular County Scraper Factory
"""

import asyncio
import json
import click
from pathlib import Path
from datetime import datetime, timedelta

from scraper_factory import ScraperFactory
from config_schemas import CountyConfig

@click.command()
@click.option('--max-records', default=100, help='Maximum records to scrape')
@click.option('--date-from', help='Start date (YYYY-MM-DD)')
@click.option('--date-to', help='End date (YYYY-MM-DD)')
@click.option('--output', help='Output file path')
@click.option('--test', is_flag=True, help='Run in test mode')
@click.option('--headless/--no-headless', default=True, help='Run browser in headless mode')
async def scrape(max_records, date_from, date_to, output, test, headless):
    """Run {config.name} scraper"""
    
    print(f"🚀 Starting {{config.name}} scraper...")
    
    # Load configuration
    config_file = "{config.name.lower().replace(' ', '_')}.json"
    config = CountyConfig.from_json_file(config_file)
    config.headless = headless
    
    # Set up task parameters
    task_params = {{
        'max_records': max_records,
        'test_mode': test
    }}
    
    if date_from or date_to:
        task_params['date_range'] = {{
            'from': date_from or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            'to': date_to or datetime.now().strftime('%Y-%m-%d')
        }}
    
    # Create and run scraper
    factory = ScraperFactory()
    result = await factory.execute_scraping(config, task_params)
    
    if result.success:
        print(f"✅ Successfully scraped {{len(result.records)}} records in {{result.execution_time:.2f}} seconds")
        
        # Save results
        if not output:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output = f"results_{config.name.lower().replace(' ', '_')}_{{timestamp}}.json"
        
        with open(output, 'w') as f:
            json.dump([record.data for record in result.records], f, indent=2, default=str)
        
        print(f"📄 Results saved to {{output}}")
        
        # Show summary
        print("\\n📊 Summary:")
        print(f"  • Records found: {{len(result.records)}}")
        print(f"  • Pages scraped: {{result.total_pages_scraped}}")
        print(f"  • Execution time: {{result.execution_time:.2f}}s")
        
    else:
        print(f"❌ Scraping failed: {{result.error_message}}")
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(scrape()))
'''

def generate_class_scraper_template(config: CountyConfig) -> str:
    """Generate class-based scraper template"""
    return f'''#!/usr/bin/env python3
"""
{config.name} Class-Based Scraper
Generated by Modular County Scraper Factory
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

from scraper_factory import ScraperFactory
from config_schemas import CountyConfig, ScrapingResult

class {config.name.replace(' ', '')}Scraper:
    """Custom scraper for {config.name}"""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file or "{config.name.lower().replace(' ', '_')}.json"
        self.config = CountyConfig.from_json_file(self.config_file)
        self.factory = ScraperFactory()
    
    async def scrape_recent(self, days: int = 30, max_records: int = 100) -> ScrapingResult:
        """Scrape records from the last N days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        return await self.scrape_date_range(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            max_records
        )
    
    async def scrape_date_range(self, date_from: str, date_to: str, max_records: int = 100) -> ScrapingResult:
        """Scrape records for a specific date range"""
        task_params = {{
            'max_records': max_records,
            'date_range': {{
                'from': date_from,
                'to': date_to
            }}
        }}
        
        return await self.factory.execute_scraping(self.config, task_params)
    
    async def scrape_with_terms(self, search_terms: List[str], max_records: int = 100) -> ScrapingResult:
        """Scrape records matching specific search terms"""
        task_params = {{
            'max_records': max_records,
            'search_terms': search_terms
        }}
        
        return await self.factory.execute_scraping(self.config, task_params)
    
    def save_results(self, result: ScrapingResult, output_file: str = None) -> str:
        """Save scraping results to file"""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"results_{config.name.lower().replace(' ', '_')}_{{timestamp}}.json"
        
        data = [record.data for record in result.records]
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        return output_file
    
    def print_summary(self, result: ScrapingResult):
        """Print scraping summary"""
        if result.success:
            print(f"✅ Scraping completed successfully!")
            print(f"  • Records found: {{len(result.records)}}")
            print(f"  • Pages scraped: {{result.total_pages_scraped}}")
            print(f"  • Execution time: {{result.execution_time:.2f}}s")
        else:
            print(f"❌ Scraping failed: {{result.error_message}}")

# Example usage
async def main():
    """Example usage of the scraper class"""
    scraper = {config.name.replace(' ', '')}Scraper()
    
    # Scrape last 7 days
    result = await scraper.scrape_recent(days=7, max_records=50)
    
    if result.success:
        # Save results
        output_file = scraper.save_results(result)
        print(f"📄 Results saved to {{output_file}}")
        
        # Print summary
        scraper.print_summary(result)
    else:
        print(f"❌ Scraping failed: {{result.error_message}}")

if __name__ == "__main__":
    asyncio.run(main())
'''

# ─────────────────────────────────────────────────────────────────────────────
# ASYNC COMMAND WRAPPERS
# ─────────────────────────────────────────────────────────────────────────────

def async_command(f):
    """Decorator to run async commands"""
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

# Apply async decorator to async commands
analyze = async_command(analyze)
run = async_command(run)
chat = async_command(chat)

if __name__ == '__main__':
    cli()