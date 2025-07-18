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
    
    def __init__(self, target_file: str = None, max_pages: int = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Core configuration
        self.target_file = target_file
        self.pages_scraped = 0
        
        # Load configurations
        self.target_config = self._load_target_config()
        
        # Override max_pages with target config if not provided
        if max_pages is None:
            self.max_pages = self.target_config.get('crawl_settings', {}).get('max_pages', 10)
        else:
            self.max_pages = max_pages
        
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
    
    def _setup_spider(self):
        """Configure spider based on target configuration."""
        if not self.target_config:
            self.logger.warning("No target configuration - spider may not work properly")
            return
        
        # Set start URLs from target config
        self.start_urls = self.target_config.get('start_urls', [])
        
        # Configure allowed domains from crawl_settings
        crawl_settings = self.target_config.get('crawl_settings', {})
        allowed_domains = crawl_settings.get('allowed_domains', [])
        
        if allowed_domains:
            self.allowed_domains = allowed_domains
        elif self.start_urls:
            # Auto-detect domains from start URLs
            from urllib.parse import urlparse
            domains = []
            for url in self.start_urls:
                domain = urlparse(url).netloc
                if domain not in domains:
                    domains.append(domain)
            self.allowed_domains = domains
        
        # Configure request settings
        request_settings = self.target_config.get('request_settings', {})
        
        # Update custom settings based on target config
        if request_settings:
            self.custom_settings = {
                'ROBOTSTXT_OBEY': True,
                'DOWNLOAD_DELAY': request_settings.get('delay', 1.0),
                'RANDOMIZE_DOWNLOAD_DELAY': 0.5 if request_settings.get('randomize_delay', True) else 0,
                'CONCURRENT_REQUESTS': request_settings.get('concurrent_requests', 1),
                'CONCURRENT_REQUESTS_PER_DOMAIN': request_settings.get('concurrent_requests', 1),
                'DOWNLOAD_TIMEOUT': request_settings.get('timeout', 30),
                'RETRY_TIMES': request_settings.get('retries', 3),
                'USER_AGENT': request_settings.get('user_agent', 'EthoScraper/1.0 (+https://github.com/maybol283/ethoscraper)'),
                'AUTOTHROTTLE_ENABLED': True,
                'AUTOTHROTTLE_START_DELAY': request_settings.get('delay', 1.0),
                'AUTOTHROTTLE_MAX_DELAY': 10,
                'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
                'HTTPCACHE_ENABLED': True,
                'HTTPCACHE_EXPIRATION_SECS': 3600,
            }
        
        # Set up link extraction rules
        self._setup_link_extraction_rules()
        
        # Get other configurations
        self.job_name = self.target_config.get('job_name', 'ethoscraper_job')
        self.extract_fields = self.target_config.get('extract_fields', {})
        self.output_config = self.target_config.get('output', {})
        self.filters = self.target_config.get('filters', {})
        self.max_depth = crawl_settings.get('max_depth', 1)
        self.follow_links = crawl_settings.get('follow_links', True)
    
    def _setup_link_extraction_rules(self):
        """Configure link extraction rules based on target config."""
        link_config = self.target_config.get('link_extraction', {})
        
        if not self.follow_links:
            self.rules = ()
            return
        
        # Build allow and deny patterns
        follow_paths = link_config.get('follow_paths', [])
        ignore_paths = link_config.get('ignore_paths', [])
        ignore_extensions = link_config.get('ignore_extensions', [])
        
        # Convert paths to regex patterns
        allow_patterns = []
        for path in follow_paths:
            # Convert simple path to regex
            pattern = f".*{re.escape(path)}.*"
            allow_patterns.append(pattern)
        
        deny_patterns = []
        for path in ignore_paths:
            pattern = f".*{re.escape(path)}.*"
            deny_patterns.append(pattern)
        
        # Add extension patterns
        for ext in ignore_extensions:
            pattern = f".*\\{ext}$"
            deny_patterns.append(pattern)
        
        # Set up rules
        self.rules = (
            Rule(
                LinkExtractor(
                    allow=allow_patterns if allow_patterns else r'.*',
                    deny=deny_patterns if deny_patterns else [],
                    restrict_css=link_config.get('css_selectors', [])
                ),
                callback='parse_item',
                follow=True
            ),
        )
    
    def setup_logging(self):
        """Set up detailed logging for compliance tracking."""
        # Get log file path from monitoring config
        monitoring = self.target_config.get('monitoring', {})
        log_file = monitoring.get('log_file', f'{self.job_name}.log')
        
        # Replace placeholders
        log_file = log_file.replace('{job_name}', self.job_name)
        log_file = log_file.replace('{timestamp}', datetime.now().strftime('%Y%m%d_%H%M%S'))
        
        # Create log directory if needed
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        log_format = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler(log_file),
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
                    'start_time': time.time(),
                    'depth': 0
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
        
        # Check depth limit
        current_depth = response.meta.get('depth', 0)
        if current_depth >= self.max_depth:
            self.logger.info(f"Reached maximum depth limit ({self.max_depth})")
            return
        
        self.pages_scraped += 1
        
        # Log the request
        self.logger.info(f"Parsing page {self.pages_scraped}/{self.max_pages}: {response.url}")
        
        # Extract data using target configuration
        item = self.extract_configured_data(response)
        
        # Apply filters
        if self._should_include_item(item):
            # Apply data protection measures
            item = self.apply_data_protection(item)
            
            # Store the data
            self.scraped_data.append(item)
            
            yield item
        else:
            self.logger.info(f"Item filtered out: {response.url}")
    
    def extract_configured_data(self, response) -> Dict[str, Any]:
        """Extract data using the new target configuration format."""
        item = {}
        
        # Extract each configured field
        for field_name, field_config in self.extract_fields.items():
            try:
                # Handle new nested configuration format
                if isinstance(field_config, dict):
                    value = self._extract_nested_field(response, field_config)
                else:
                    # Fallback for old string format
                    value = self._extract_with_selector(response, field_config)
                
                # Apply default value if needed
                if value is None:
                    value = field_config.get('default_value') if isinstance(field_config, dict) else None
                
                # Validate if required
                if isinstance(field_config, dict) and field_config.get('required', False) and not value:
                    self.logger.warning(f"Required field '{field_name}' is missing")
                
                # Field-level validation
                if value and isinstance(field_config, dict) and 'validation' in field_config:
                    if not self._validate_field_value(value, field_config['validation']):
                        self.logger.warning(f"Field '{field_name}' failed validation")
                        continue
                
                item[field_name] = value
                
            except Exception as e:
                self.logger.warning(f"Error extracting field '{field_name}': {e}")
                error_value = '[ERROR]'
                if isinstance(field_config, dict):
                    error_value = field_config.get('default_value', '[ERROR]')
                item[field_name] = error_value
        
        # Add metadata
        item['scraped_at'] = datetime.now().isoformat()
        item['source_url'] = response.url
        item['response_time'] = response.meta.get('download_latency', 0)
        
        return item
    
    def _extract_nested_field(self, response, field_config: Dict) -> Any:
        """Extract data using nested field configuration."""
        selector = field_config.get('selector', '')
        
        # Handle special cases
        if selector == "response.url":
            value = response.url
        else:
            # Extract using CSS selector
            if '::text' in selector:
                values = response.css(selector).getall()
            elif '::attr(' in selector:
                values = response.css(selector).getall()
            else:
                # Default to text extraction
                values = response.css(f"{selector}::text").getall()
            
            # Apply transformations
            transformations = field_config.get('transformations', [])
            values = self._apply_nested_transformations(values, transformations)
            
            # Return appropriate format
            if len(values) == 1:
                value = values[0]
            elif len(values) == 0:
                value = None
            else:
                value = values
        
        return value
    
    def _apply_nested_transformations(self, values: List[str], transformations: List[Dict]) -> List[str]:
        """Apply transformations using new nested format."""
        if not values:
            return values
        
        for transform in transformations:
            for transform_type, transform_config in transform.items():
                if transform_type == 'strip' and transform_config:
                    values = [v.strip() for v in values if v]
                
                elif transform_type == 'lowercase' and transform_config:
                    values = [v.lower() for v in values]
                
                elif transform_type == 'uppercase' and transform_config:
                    values = [v.upper() for v in values]
                
                elif transform_type == 'title_case' and transform_config:
                    values = [v.title() for v in values]
                
                elif transform_type == 'limit':
                    values = values[:transform_config]
                
                elif transform_type == 'join':
                    values = [transform_config.join(values)]
                
                elif transform_type == 'split':
                    new_values = []
                    for v in values:
                        new_values.extend(v.split(transform_config))
                    values = new_values
                
                elif transform_type == 'replace':
                    from_val = transform_config.get('from', '')
                    to_val = transform_config.get('to', '')
                    values = [v.replace(from_val, to_val) for v in values]
                
                elif transform_type == 'truncate':
                    values = [v[:transform_config] for v in values]
                
                elif transform_type == 'remove_html' and transform_config:
                    values = [re.sub(r'<[^>]+>', '', v) for v in values]
                
                elif transform_type == 'remove_prefix':
                    values = [v[len(transform_config):] if v.startswith(transform_config) else v for v in values]
                
                elif transform_type == 'remove_suffix':
                    values = [v[:-len(transform_config)] if v.endswith(transform_config) else v for v in values]
                
                elif transform_type == 'normalize_phone' and transform_config:
                    values = [self._normalize_phone(v) for v in values]
        
        return values
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number format."""
        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone)
        
        # Basic normalization - you can extend this
        if cleaned.startswith('+'):
            return cleaned
        elif len(cleaned) == 10:
            return f"+1{cleaned}"
        elif len(cleaned) == 11 and cleaned.startswith('1'):
            return f"+{cleaned}"
        else:
            return phone
    
    def _validate_field_value(self, value: Any, validation: Dict) -> bool:
        """Validate field value against validation rules."""
        if not value:
            return True
        
        value_str = str(value)
        
        # Pattern validation
        if 'pattern' in validation:
            if not re.match(validation['pattern'], value_str):
                return False
        
        # Length validation
        if 'min_length' in validation:
            if len(value_str) < validation['min_length']:
                return False
        
        if 'max_length' in validation:
            if len(value_str) > validation['max_length']:
                return False
        
        return True
    
    def _should_include_item(self, item: Dict[str, Any]) -> bool:
        """Check if item should be included based on filters."""
        exclude_rules = self.filters.get('exclude_if', [])
        
        for rule in exclude_rules:
            field = rule.get('field')
            contains = rule.get('contains')
            
            if field in item and item[field] and contains:
                if contains.lower() in str(item[field]).lower():
                    return False
        
        return True
    
    def apply_data_protection(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Apply data protection measures based on field-level privacy settings."""
        
        # Apply field-level privacy settings
        for field_name, field_config in self.extract_fields.items():
            if isinstance(field_config, dict) and 'privacy' in field_config:
                privacy_config = field_config['privacy']
                
                if field_name in item and item[field_name]:
                    # Apply pseudonymization
                    if 'pseudonymise' in privacy_config:
                        method = privacy_config['pseudonymise']
                        if method.startswith('SHA256'):
                            hash_full = hashlib.sha256(str(item[field_name]).encode()).hexdigest()
                            if ':' in method:
                                length = int(method.split(':')[1])
                                item[field_name] = hash_full[:length]
                            else:
                                item[field_name] = hash_full
                        elif method == 'Stub':
                            item[field_name] = '[REDACTED]'
                    
                    # Apply anonymization (remove field completely)
                    if privacy_config.get('anonymize', False):
                        item.pop(field_name, None)
        
        return item
    
    def save_results(self):
        """Save scraped data to file based on output configuration."""
        if not self.scraped_data:
            self.logger.warning("No data to save")
            return
        
        # Get output configuration
        output_file = self.output_config.get('file', f'output/scraped_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        
        # Replace placeholders
        output_file = output_file.replace('{timestamp}', datetime.now().strftime('%Y%m%d_%H%M%S'))
        output_file = output_file.replace('{job_name}', self.job_name)
        
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
    
    def closed(self, reason):
        """Called when spider is closed."""
        end_time = datetime.now()
        duration = end_time - self.start_time
        
        self.logger.info(f"Spider closed: {reason}")
        self.logger.info(f"Pages scraped: {self.pages_scraped}")
        self.logger.info(f"Duration: {duration}")
        
        # Save final results
        self.save_results()
    
    # Legacy method for backward compatibility
    def _extract_with_selector(self, response, selector_config: str) -> Any:
        """Extract data using old selector string format."""
        if selector_config == "response.url":
            return response.url
        
        parts = selector_config.split(' | ')
        selector = parts[0]
        transformations = parts[1:] if len(parts) > 1 else []
        
        if '::text' in selector:
            values = response.css(selector).getall()
        elif '::attr(' in selector:
            values = response.css(selector).getall()
        else:
            values = response.css(f"{selector}::text").getall()
        
        for transform in transformations:
            values = self._apply_transformation(values, transform.strip())
        
        if len(values) == 1:
            return values[0]
        elif len(values) == 0:
            return None
        else:
            return values
    
    def _apply_transformation(self, values: List[str], transformation: str) -> List[str]:
        """Apply old-style transformations for backward compatibility."""
        if transformation == 'strip':
            return [v.strip() for v in values if v]
        elif transformation.startswith('replace:'):
            parts = transformation.split(':', 1)[1].split(',')
            if len(parts) == 2:
                old = parts[0].strip().strip('"\'')
                new = parts[1].strip().strip('"\'')
                return [v.replace(old, new) for v in values]
        elif transformation == 'join':
            return [' '.join(values)]
        elif transformation.startswith('regex:'):
            pattern = transformation.split(':', 1)[1]
            return [re.sub(pattern, '', v) for v in values]
        
        return values


def run_ethical_scraper(target_file: str, max_pages: int = None, **kwargs):
    """
    Run the ethical scraper with target configuration.
    
    Args:
        target_file: Path to target.yaml configuration file
        max_pages: Maximum number of pages to scrape (overrides config)
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
        max_pages=max_pages,
        **kwargs
    )
    process.start()


# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <target.yaml> [max_pages]")
        sys.exit(1)
    
    target_file = sys.argv[1]
    max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    print(f"🎯 Starting targeted scraping with: {target_file}")
    print(f"📄 Max pages: {max_pages or 'From config'}")
    print("-" * 50)
    
    run_ethical_scraper(target_file, max_pages)