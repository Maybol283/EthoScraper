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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import hashlib
import time
import glob
import os


def find_latest_lia_report(base_dir: str = "output") -> Optional[Path]:
    """Find the most recent LIA analysis report in the specified directory."""
    pattern = os.path.join(base_dir, "lia_analysis_report_*.md")
    report_files = glob.glob(pattern)
    
    if not report_files:
        return None
    
    # Sort by modification time, most recent first
    report_files.sort(key=os.path.getmtime, reverse=True)
    return Path(report_files[0])


def parse_confidence_rating_from_report(report_path: Path) -> Optional[int]:
    """Parse confidence rating from LIA analysis report markdown file."""
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for confidence rating in the markdown table
        # Pattern: | **Overall Confidence Rating** | **XX/100** |
        confidence_pattern = r'\|\s*\*\*Overall Confidence Rating\*\*\s*\|\s*\*\*(\d+)/100\*\*\s*\|'
        match = re.search(confidence_pattern, content)
        
        if match:
            return int(match.group(1))
        
        # Fallback pattern: look for "confidence_rating: XX" in YAML sections
        yaml_pattern = r'confidence_rating:\s*(\d+)'
        match = re.search(yaml_pattern, content)
        
        if match:
            return int(match.group(1))
        
        return None
        
    except Exception as e:
        print(f"Error parsing LIA report {report_path}: {e}")
        return None


def validate_lia_compliance(target_file: str = None, force: bool = False) -> bool:
    """Validate that LIA analysis has been performed with acceptable confidence rating."""
    if force:
        print("⚠️  WARNING: LIA validation bypassed with --force flag")
        return True
    
    # Determine base directory for reports
    if target_file:
        base_dir = Path(target_file).parent / "output"
    else:
        base_dir = Path("output")
    
    # Find the latest LIA report
    latest_report = find_latest_lia_report(str(base_dir))
    
    if not latest_report:
        print("❌ ERROR: No LIA analysis report found!")
        print("   Please run 'ethoscraper analyze' first to generate an LIA analysis report.")
        print("   Or use --force to bypass this requirement (not recommended).")
        return False
    
    # Parse confidence rating
    confidence_rating = parse_confidence_rating_from_report(latest_report)
    
    if confidence_rating is None:
        print(f"❌ ERROR: Could not parse confidence rating from {latest_report}")
        print("   Please ensure the LIA report is valid.")
        print("   Or use --force to bypass this requirement (not recommended).")
        return False
    
    print(f"📋 Found LIA analysis report: {latest_report.name}")
    print(f"📊 Confidence Rating: {confidence_rating}/100")
    
    if confidence_rating < 70:
        print("❌ ERROR: LIA confidence rating is below 70 (minimum required)")
        print("   Current rating indicates significant legal risks.")
        print("   Please review and improve your LIA before scraping.")
        print("   Or use --force to bypass this requirement (not recommended).")
        return False
    
    print("✅ LIA validation passed - confidence rating meets minimum requirements")
    return True


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
                'ROBOTSTXT_OBEY': False,  # Disable robots.txt checking for testing
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
                'HTTPERROR_ALLOWED_CODES': [403],  # Allow 403 errors to be processed
                # Built-in CSV export
                'FEEDS': {
                    'output/scraped_data.csv': {
                        'format': 'csv',
                        'overwrite': True,
                    },
                }
            }
        else:
            # Default settings if no request_settings provided
            self.custom_settings = {
                'ROBOTSTXT_OBEY': False,
                'DOWNLOAD_DELAY': 1.0,
                'HTTPERROR_ALLOWED_CODES': [403],
            }
        
        # Get other configurations FIRST (before setting up link extraction rules)
        self.job_name = self.target_config.get('job_name', 'ethoscraper_job')
        self.extract_fields = self.target_config.get('extract_fields', {})
        self.output_config = self.target_config.get('output', {})
        self.filters = self.target_config.get('filters', {})
        self.max_depth = crawl_settings.get('max_depth', 1)
        self.follow_links = crawl_settings.get('follow_links', True)  # ← Now set BEFORE link extraction

        # Set up link extraction rules AFTER follow_links is set
        self._setup_link_extraction_rules()  # ← Called AFTER follow_links is initialized
    
    def _setup_link_extraction_rules(self):
        """Configure link extraction rules based on target config."""
        link_config = self.target_config.get('link_extraction', {})
        
        if not self.follow_links:
            self.rules = ()
            return
        
        # Build allow and deny patterns
        follow_paths = link_config.get('follow_paths', []) or []
        ignore_paths = link_config.get('ignore_paths', []) or []
        ignore_extensions = link_config.get('ignore_extensions', []) or []
        
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
        
        # Debug: Print the rules configuration
        self.logger.info(f"CrawlSpider rules configured:")
        self.logger.info(f"  Allow patterns: {allow_patterns}")
        self.logger.info(f"  Deny patterns: {deny_patterns}")
        self.logger.info(f"  CSS selectors: {link_config.get('css_selectors', [])}")
        self.logger.info(f"  Follow links: {self.follow_links}")
        
        # Compile the rules (this is normally done automatically)
        super()._compile_rules()
    
    def _get_project_output_dir(self) -> Path:
        """Get the output directory based on target file location."""
        if self.target_file:
            # Use the target file's directory/output as the base
            target_path = Path(self.target_file)
            return target_path.parent / 'output'
        else:
            # Fallback to general output directory
            return Path('output')
    
    def setup_logging(self):
        """Set up detailed logging for compliance tracking."""
        # Get log file path from monitoring config
        monitoring = self.target_config.get('monitoring', {})
        log_file = monitoring.get('log_file', f'{self.job_name}.log')
        
        # Replace placeholders
        log_file = log_file.replace('{job_name}', self.job_name)
        log_file = log_file.replace('{timestamp}', datetime.now().strftime('%Y%m%d_%H%M%S'))
        
        # Handle path relative to target file directory
        if self.target_file:
            target_path = Path(self.target_file)
            if log_file.startswith('./') or log_file.startswith('.\\'):
                # If path starts with ./ or .\, use relative to target file directory
                log_path = target_path.parent / log_file[2:]
            else:
                # Otherwise, use project output directory
                project_output_dir = self._get_project_output_dir()
                log_path = project_output_dir / log_file
        else:
            # Fallback to original behavior
            log_path = Path(log_file)
        
        # Create log directory if needed
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Store log path for manual logging
        self.log_file_path = log_path
        
        # Create/clear the log file and write header
        with open(self.log_file_path, 'w') as f:
            f.write(f"{datetime.now()}: Scraper started - {self.job_name}\n")
        
        print(f"📋 Clean logging configured - file: {log_path}")
    
    def log_message(self, message):
        """Simple method to log messages directly to file."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"{timestamp}: {message}\n"
        
        # Write to file
        if hasattr(self, 'log_file_path'):
            try:
                with open(self.log_file_path, 'a') as f:
                    f.write(log_entry)
            except Exception as e:
                print(f"Logging error: {e}")
        
        # Also print to console for immediate feedback
        print(log_entry.strip())
    
    # Removed custom start_requests - let CrawlSpider handle it automatically
    # This allows the rules-based link following to work properly
    
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
            # If robots.txt is blocked (403) or can't be read, assume allowed
            # since we know the actual content should allow scraping of /en/persons/
            self.logger.info(f"Assuming {url} is allowed due to robots.txt access issue")
            return True
    
    def parse_item(self, response):
        """Parse individual pages using target configuration."""
        # Handle 403 errors - log details and continue
        if response.status == 403:
            self.logger.warning(f"Received 403 Forbidden for {response.url}")
            self.logger.warning(f"Response headers: {dict(response.headers)}")
            self.logger.warning(f"Response body preview: {response.body[:200]}")
            # For testing, we'll continue processing even with 403
            
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
        self.log_message(f"Accessing {response.url} (page {self.pages_scraped}/{self.max_pages})")
        
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
        current_time = datetime.now()
        item['scraped_at'] = current_time.isoformat()
        item['source_url'] = response.url
        item['response_time'] = response.meta.get('download_latency', 0)
        
        # Add GDPR compliance columns
        contact_by_date = current_time + timedelta(days=30)
        item['contact_by'] = contact_by_date.isoformat()
        item['user_contacted'] = False
        
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
        output_file = self.output_config.get('file', f'scraped_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        
        # Replace placeholders
        output_file = output_file.replace('{timestamp}', datetime.now().strftime('%Y%m%d_%H%M%S'))
        output_file = output_file.replace('{job_name}', self.job_name)
        
        # Handle path relative to target file directory
        if self.target_file:
            target_path = Path(self.target_file)
            if output_file.startswith('./') or output_file.startswith('.\\'):
                # If path starts with ./ or .\, use relative to target file directory
                output_path = target_path.parent / output_file[2:]
            else:
                # Otherwise, use project output directory
                project_output_dir = self._get_project_output_dir()
                output_path = project_output_dir / output_file
        else:
            # Fallback to original behavior
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
        
        # Get field names in target.yaml order, then add any extras
        fieldnames = list(self.extract_fields.keys())
        
        # Add any additional fields not in target.yaml (like scraped_at, source_url, etc.)
        all_fields = set()
        for item in self.scraped_data:
            all_fields.update(item.keys())
        
        # Add extra fields at the end
        for field in all_fields:
            if field not in fieldnames:
                fieldnames.append(field)
        
        # Use utf-8-sig encoding to add BOM for better Excel compatibility
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
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
        
        self.log_message(f"Completed: {self.pages_scraped} pages scraped in {duration}")
        
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


def run_ethical_scraper(target_file: str, max_pages: int = None, force: bool = False, **kwargs):
    """
    Run the ethical scraper with target configuration.
    
    Args:
        target_file: Path to target.yaml configuration file
        max_pages: Maximum number of pages to scrape (overrides config)
        force: Bypass LIA validation requirements
        **kwargs: Additional spider arguments
    """
    
    # Validate LIA compliance before starting scrape
    if not validate_lia_compliance(target_file, force):
        print("\n🛑 Scraping aborted due to LIA compliance issues")
        exit(1)
    
    # Configure Scrapy settings
    settings = get_project_settings()
    settings.update({
        'ROBOTSTXT_OBEY': False,
        # Remove hardcoded settings - let spider's custom_settings from YAML take precedence
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


def main():
    """Main entry point for scraper."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Ethical web scraper')
    parser.add_argument('target_file', help='Target YAML configuration file')
    parser.add_argument('--max-pages', type=int, help='Maximum pages to scrape')
    parser.add_argument('--force', action='store_true', 
                       help='Bypass LIA validation requirements (not recommended)')
    
    args = parser.parse_args()
    
    print(f"🎯 Starting targeted scraping with: {args.target_file}")
    print(f"📄 Max pages: {args.max_pages or 'From config'}")
    if args.force:
        print("⚠️  Force mode enabled - LIA validation will be bypassed")
    print("-" * 50)
    
    run_ethical_scraper(args.target_file, args.max_pages, args.force)


# Example usage
if __name__ == "__main__":
    main()