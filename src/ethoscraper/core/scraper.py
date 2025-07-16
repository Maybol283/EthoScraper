#!/usr/bin/env python3
"""
EthoScraper - Ethical Scrapy Spider with Target Configuration
"""

import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from scrapy.exceptions import CloseSpider
from urllib.robotparser import RobotFileParser
from pathlib import Path
import yaml
import json
import csv
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
import hashlib
import time


class EthicalSpider(CrawlSpider):
    """
    Ethical web scraper that uses target.yaml configuration for specific extraction.
    """
    
    name = 'ethical_spider'
    
    # Default settings - can be overridden
    custom_settings = {
        'ROBOTSTXT_OBEY': True,
        'DOWNLOAD_DELAY': 1,  # 1 second delay between requests
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,  # Random delay (0.5 * to 1.5 * DOWNLOAD_DELAY)
        'CONCURRENT_REQUESTS': 1,  # Be respectful - only 1 concurrent request
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 1,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
        'USER_AGENT': 'EthoScraper/1.0 (+https://github.com/maybol283/ethoscraper)',
        'HTTPCACHE_ENABLED': True,
        'HTTPCACHE_EXPIRATION_SECS': 3600,  # Cache for 1 hour
    }
    
    def __init__(self, target_file: str = None, compliance_file: str = None, 
                 max_pages: int = 10, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Core configuration
        self.target_file = target_file
        self.compliance_file = compliance_file
        self.max_pages = max_pages
        self.pages_scraped = 0
        
        # Load configurations
        self.target_config = self._load_target_config()
        self.compliance_config = self._load_compliance_config()
        
        # Set up spider based on target config
        self._setup_spider()
        
        # Initialize data storage
        self.scraped_data = []
        self.start_time = datetime.now()
        
        # Set up logging
        self.setup_logging()
    
    def _load_target_config(self) -> Dict:
        """Load target configuration from YAML file."""
        if not self.target_file:
            self.logger.warning("No target file specified - using default settings")
            return {}
        
        try:
            with open(self.target_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.logger.info(f"Loaded target config: {config.get('job_name', 'Unknown')}")
                return config
        except FileNotFoundError:
            self.logger.error(f"Target file not found: {self.target_file}")
            return {}
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing target file: {e}")
            return {}
    
    def _load_compliance_config(self) -> Dict:
        """Load compliance configuration from YAML file."""
        if not self.compliance_file:
            return {}
        
        try:
            with open(self.compliance_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.error(f"Compliance file not found: {self.compliance_file}")
            return {}
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing compliance file: {e}")
            return {}
    
    def _setup_spider(self):
        """Configure spider based on target configuration."""
        if not self.target_config:
            self.logger.warning("No target configuration - spider may not work properly")
            return
        
        # Set start URLs from target config
        self.start_urls = self.target_config.get('start_urls', [])
        
        # Configure allowed domains
        if self.start_urls:
            from urllib.parse import urlparse
            domains = []
            for url in self.start_urls:
                domain = urlparse(url).netloc
                if domain not in domains:
                    domains.append(domain)
            self.allowed_domains = domains
        
        # Set up rules for crawling if needed
        self.rules = (
            Rule(
                LinkExtractor(
                    allow=r'.*',
                    deny=r'.*\.(pdf|doc|docx|xls|xlsx|ppt|pptx|zip|rar|tar|gz)$',
                ),
                callback='parse_item',
                follow=True
            ),
        )
        
        # Get job name
        self.job_name = self.target_config.get('job_name', 'ethoscraper_job')
        
        # Get extraction fields
        self.extract_fields = self.target_config.get('extract_fields', {})
        
        # Get output configuration
        self.output_config = self.target_config.get('output', {})
    
    def setup_logging(self):
        """Set up detailed logging for compliance tracking."""
        log_format = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler(f'{self.job_name}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(self.name)
    
    def start_requests(self):
        """Generate initial requests with compliance checks."""
        if not self.start_urls:
            raise CloseSpider("No start URLs provided in target configuration")
        
        # Check robots.txt compliance for each URL
        for url in self.start_urls:
            if not self._check_robots_txt(url):
                self.logger.warning(f"Robots.txt check failed for: {url}")
                continue
        
        self.logger.info(f"Starting ethical scraping of {len(self.start_urls)} URLs")
        
        for url in self.start_urls:
            yield scrapy.Request(
                url=url,
                callback=self.parse_item,
                meta={
                    'compliance_checked': True,
                    'start_time': time.time()
                }
            )
    
    def _check_robots_txt(self, url: str) -> bool:
        """Check if scraping is allowed by robots.txt for a specific URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            user_agent = self.custom_settings.get('USER_AGENT', '*')
            allowed = rp.can_fetch(user_agent, url)
            
            self.logger.info(f"Robots.txt check for {url}: {'ALLOWED' if allowed else 'BLOCKED'}")
            return allowed
            
        except Exception as e:
            self.logger.warning(f"Could not check robots.txt for {url}: {e}")
            return True  # Assume allowed if can't check
    
    def parse_item(self, response):
        """Parse individual pages using target configuration."""
        # Check page limit
        if self.pages_scraped >= self.max_pages:
            self.logger.info(f"Reached maximum pages limit ({self.max_pages})")
            raise CloseSpider("Maximum pages reached")
        
        self.pages_scraped += 1
        
        # Log the request
        self.logger.info(f"Parsing page {self.pages_scraped}/{self.max_pages}: {response.url}")
        
        # Extract data using target configuration
        item = self.extract_configured_data(response)
        
        # Apply data protection measures
        item = self.apply_data_protection(item)
        
        # Store the data
        self.scraped_data.append(item)
        
        yield item
    
    def extract_configured_data(self, response) -> Dict[str, Any]:
        """Extract data using the target configuration selectors."""
        item = {}
        
        # Extract each configured field
        for field_name, selector_config in self.extract_fields.items():
            if field_name in ['placeholder_value', 'pseudonymise']:
                continue  # Skip configuration fields
            
            try:
                # Handle different selector formats
                if isinstance(selector_config, str):
                    value = self._extract_with_selector(response, selector_config)
                elif isinstance(selector_config, dict):
                    # Handle complex selector configurations
                    value = self._extract_complex_field(response, selector_config)
                else:
                    value = None
                
                item[field_name] = value
                
            except Exception as e:
                self.logger.warning(f"Error extracting field '{field_name}': {e}")
                item[field_name] = self.extract_fields.get('placeholder_value', '[ERROR]')
        
        # Add metadata
        item['scraped_at'] = datetime.now().isoformat()
        item['source_url'] = response.url
        item['response_time'] = response.meta.get('download_latency', 0)
        
        return item
    
    def _extract_with_selector(self, response, selector_config: str) -> Any:
        """Extract data using a selector string with optional transformations."""
        
        # Check for special case: response.url
        if selector_config == "response.url":
            return response.url
        
        # Parse selector with transformations
        parts = selector_config.split(' | ')
        selector = parts[0]
        transformations = parts[1:] if len(parts) > 1 else []
        
        # Extract data using CSS selector
        if '::text' in selector:
            values = response.css(selector).getall()
        elif '::attr(' in selector:
            values = response.css(selector).getall()
        else:
            # Default to text extraction
            values = response.css(f"{selector}::text").getall()
        
        # Apply transformations
        for transform in transformations:
            values = self._apply_transformation(values, transform.strip())
        
        # Return single value or list
        if len(values) == 1:
            return values[0]
        elif len(values) == 0:
            return None
        else:
            return values
    
    def _apply_transformation(self, values: List[str], transformation: str) -> List[str]:
        """Apply a transformation to extracted values."""
        if transformation == 'strip':
            return [v.strip() for v in values if v]
        elif transformation.startswith('replace:'):
            # Parse replace: 'old', 'new'
            parts = transformation.split(':', 1)[1].split(',')
            if len(parts) == 2:
                old = parts[0].strip().strip('"\'')
                new = parts[1].strip().strip('"\'')
                return [v.replace(old, new) for v in values]
        elif transformation == 'join':
            return [' '.join(values)]
        elif transformation.startswith('regex:'):
            # Apply regex transformation
            pattern = transformation.split(':', 1)[1]
            return [re.sub(pattern, '', v) for v in values]
        
        return values
    
    def _extract_complex_field(self, response, field_config: Dict) -> Any:
        """Handle complex field configurations."""
        # This can be extended for more complex extraction logic
        return None
    
    def apply_data_protection(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Apply data protection measures based on target and compliance config."""
        
        # Apply pseudonymization from target config
        pseudonymise_config = self.extract_fields.get('pseudonymise', {})
        
        for field, method in pseudonymise_config.items():
            if field in item and item[field]:
                if method.startswith('SHA256'):
                    # Handle SHA256:8 format (truncate to 8 characters)
                    hash_full = hashlib.sha256(str(item[field]).encode()).hexdigest()
                    if ':' in method:
                        length = int(method.split(':')[1])
                        item[field] = hash_full[:length]
                    else:
                        item[field] = hash_full
                elif method == 'Stub':
                    item[field] = '[REDACTED]'
        
        # Apply compliance-based data protection if available
        if self.compliance_config:
            protection_settings = self.compliance_config.get('data_protection', {})
            
            # Drop fields if configured in compliance
            dropped_columns = protection_settings.get('columns_dropped', [])
            for column in dropped_columns:
                item.pop(column, None)
        
        return item
    
    def closed(self, reason):
        """Called when spider is closed."""
        end_time = datetime.now()
        duration = end_time - self.start_time
        
        self.logger.info(f"Spider closed: {reason}")
        self.logger.info(f"Pages scraped: {self.pages_scraped}")
        self.logger.info(f"Duration: {duration}")
        
        # Save final results
        self.save_results()
    
    def save_results(self):
        """Save scraped data to file based on output configuration."""
        if not self.scraped_data:
            self.logger.warning("No data to save")
            return
        
        # Get output configuration
        output_file = self.output_config.get('file', f'output/scraped_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        output_path = Path(output_file)
        
        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Determine file format based on extension
        file_extension = output_path.suffix.lower()
        
        try:
            if file_extension == '.csv':
                self._save_as_csv(output_path)
            elif file_extension == '.yaml' or file_extension == '.yml':
                self._save_as_yaml(output_path)
            else:
                self._save_as_json(output_path)
            
            self.logger.info(f"✅ Data saved to {output_path}")
            
        except Exception as e:
            self.logger.error(f"Error saving data: {e}")
    
    def _save_as_csv(self, output_path: Path):
        """Save data as CSV file."""
        if not self.scraped_data:
            return
        
        # Get all field names
        fieldnames = set()
        for item in self.scraped_data:
            fieldnames.update(item.keys())
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(fieldnames))
            writer.writeheader()
            writer.writerows(self.scraped_data)
    
    def _save_as_yaml(self, output_path: Path):
        """Save data as YAML file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.scraped_data, f, default_flow_style=False, indent=2)
    
    def _save_as_json(self, output_path: Path):
        """Save data as JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.scraped_data, f, indent=2, ensure_ascii=False)


def run_ethical_scraper(target_file: str, compliance_file: str = None, 
                       max_pages: int = 10, **kwargs):
    """
    Run the ethical scraper with target configuration.
    
    Args:
        target_file: Path to target.yaml configuration file
        compliance_file: Path to compliance YAML file (optional)
        max_pages: Maximum number of pages to scrape
        **kwargs: Additional spider arguments
    """
    
    # Configure Scrapy settings
    settings = get_project_settings()
    settings.update({
        'ROBOTSTXT_OBEY': True,
        'DOWNLOAD_DELAY': 1,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS': 1,
        'USER_AGENT': 'EthoScraper/1.0 (+https://github.com/maybol283/ethoscraper)',
    })
    
    # Create and run crawler
    process = CrawlerProcess(settings)
    process.crawl(
        EthicalSpider,
        target_file=target_file,
        compliance_file=compliance_file,
        max_pages=max_pages,
        **kwargs
    )
    process.start()


# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <target.yaml> [compliance.yaml] [max_pages]")
        sys.exit(1)
    
    target_file = sys.argv[1]
    compliance_file = sys.argv[2] if len(sys.argv) > 2 else None
    max_pages = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    
    print(f"🎯 Starting targeted scraping with: {target_file}")
    print(f"📋 Compliance file: {compliance_file or 'None'}")
    print(f"📄 Max pages: {max_pages}")
    print("-" * 50)
    
    run_ethical_scraper(target_file, compliance_file, max_pages)
