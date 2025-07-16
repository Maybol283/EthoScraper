# Ethical Scraper Project

## Overview

The Ethical Scraper is designed to perform web scraping in an ethical manner, ensuring compliance with legal and ethical standards. It includes features for initial domain scanning, DPIA screening, and Legitimate Interest Assessment (LIA) to determine the ethical viability of scraping activities.
The tool aims to provide assistance to legitimate use cases of scraping and removing the barrier entry in gathering data for researchers and professionals while remaining GDPR compliant.

## Features

- **Domain Scanning**: The scraper scans a domain to determine if wildcard access is allowed and identifies rate limits set in the robots.txt file or specified by the user.
- **Setup Wizard**: Guides users through initial setup, including domain scanning and configuration of scraping parameters.
- **DPIA Screening**: Conducts a Data Protection Impact Assessment (DPIA) to evaluate the impact of scraping on data subjects and compliance with data protection regulations.
- **Legitimate Interest Assessment (LIA)**: Users answer a series of questions to assess if scraping activities align with legitimate interests under GDPR and similar regulations.
- **Confidence Rating**: Uses inputs from LIA to generate a confidence rating using a Legal Language Model (LLM) to help inform users before proceeding with scraping activities.

## Installation

As the project is a WIP installation and use guidance will be provdided upon completion

## Target Configuration (target.yaml)

The `target.yaml` file is the main configuration file for defining scraping jobs. It provides comprehensive control over all aspects of the scraping process, from URL targeting to data extraction and privacy protection.

### Basic Configuration

```yaml
job_name: "University Staff Directory"
description: "Scrape public staff directory for research collaboration"
version: "1.0"
```

- **job_name**: Human-readable name for the scraping job (used in logs and output files)
- **description**: Brief description of the scraping purpose
- **version**: Configuration version for tracking changes

### URL Configuration

```yaml
start_urls:
  - "https://university.edu/"
  - "https://example.com/staff/"
```

- **start_urls**: List of URLs where the scraper will begin crawling

### Crawling Behavior

```yaml
crawl_settings:
  max_depth: 2 # Maximum link depth to follow
  max_pages: 20 # Total page limit
  follow_links: true # Whether to follow links or just scrape start URLs
  allowed_domains: # Restrict scraping to specific domains
    - "university.edu"
    - "staff.university.edu"
```

- **max_depth**: How many levels deep to follow links (0 = start URLs only)
- **max_pages**: Maximum total pages to scrape across all URLs
- **follow_links**: Enable/disable link following
- **allowed_domains**: Domain whitelist for security

### Link Following Rules

```yaml
link_extraction:
  follow_paths: # URL paths to follow
    - "/staff/"
    - "/faculty/"
    - "/profile/"

  ignore_paths: # URL paths to avoid
    - "/admin/"
    - "/login/"

  ignore_extensions: # File extensions to skip
    - ".pdf"
    - ".doc"
    - ".zip"

  css_selectors: # Specific link elements to target
    - "a.staff-link"
    - ".pagination a"
    - "a[href*='profile']"
```

- **follow_paths**: Simple string matching for URLs to follow
- **ignore_paths**: Simple string matching for URLs to avoid
- **ignore_extensions**: Skip links to files with these extensions
- **css_selectors**: Target specific link elements on pages

### Request Settings

```yaml
request_settings:
  delay: 1.0 # Delay between requests (seconds)
  randomize_delay: true # Add random variation to delay
  concurrent_requests: 1 # Number of simultaneous requests
  timeout: 30 # Request timeout (seconds)
  retries: 3 # Number of retry attempts
  user_agent: "EthoScraper/1.0 (+https://github.com/maybol283/ethoscraper)"
```

- **delay**: Base delay between requests for respectful crawling
- **randomize_delay**: Adds 50% random variation to delay
- **concurrent_requests**: Usually 1 for ethical scraping
- **timeout**: Maximum time to wait for page response
- **retries**: Attempts to retry failed requests
- **user_agent**: Browser identification string

### Data Extraction

The `extract_fields` section defines what data to extract from each page using a structured format:

```yaml
extract_fields:
  field_name:
    selector: "css-selector" # CSS selector for data extraction
    transformations: # Data processing steps
      - strip: true # Remove whitespace
      - title_case: true # Convert to Title Case
      - replace: # Replace text
          from: "old_text"
          to: "new_text"
      - split: "," # Split string into array
      - limit: 5 # Keep only first N items
      - join: "; " # Join array with separator
      - truncate: 200 # Limit character length
      - remove_html: true # Strip HTML tags
      - normalize_phone: true # Standardize phone format
      - lowercase: true # Convert to lowercase
      - remove_prefix: "Dr. " # Remove specific prefix

    required: true # Field must have value
    default_value: "[Not Available]" # Default if no value found

    validation: # Data validation rules
      pattern: "regex-pattern" # RegEx validation
      min_length: 10 # Minimum character length
      max_length: 1000 # Maximum character length

    privacy: # Privacy protection settings
      pseudonymise: "SHA256:8" # Hash and truncate to 8 chars
      anonymize: true # Remove field completely
```

#### Common Transformation Options

- **strip**: Remove leading/trailing whitespace
- **title_case**: Convert to Title Case
- **lowercase/uppercase**: Change case
- **replace**: Replace text patterns
- **split**: Split string into array by delimiter
- **limit**: Keep only first N items from array
- **join**: Join array elements with separator
- **truncate**: Limit to maximum characters
- **remove_html**: Strip HTML tags
- **normalize_phone**: Standardize phone number format
- **remove_prefix/remove_suffix**: Remove specific text

#### Privacy Protection Options

- **pseudonymise**:
  - `"SHA256:8"` - Hash with SHA256, truncate to 8 characters
  - `"Stub"` - Replace with `[REDACTED]`
- **anonymize**: Remove field completely from output

#### Validation Options

- **pattern**: RegEx pattern for validation
- **min_length/max_length**: Character length limits
- **required**: Field must contain a value

### Content Filtering

```yaml
filters:
  exclude_if: # Skip records matching conditions
    - field: "title"
      contains: "Admin"
    - field: "department"
      contains: "IT Support"
```

- **exclude_if**: Skip records where specified field contains certain text

### Output Configuration

```yaml
output:
  file: "./output/university-staff-{timestamp}.csv"
```

- **file**: Output file path with optional `{timestamp}` placeholder
- File extension determines format (`.csv`, `.json`, `.yaml`)

### Monitoring & Logging

```yaml
monitoring:
  log_file: "./logs/{job_name}_{timestamp}.log"
```

- **log_file**: Path for detailed scraping logs with placeholders

### Example Complete Configuration

```yaml
job_name: "University Research Directory"
description: "Ethical scraping of public research profiles"
version: "1.0"

start_urls:
  - "https://university.edu/research/"

crawl_settings:
  max_depth: 3
  max_pages: 100
  follow_links: true
  allowed_domains:
    - "university.edu"

link_extraction:
  follow_paths:
    - "/research/"
    - "/faculty/"
    - "/profile/"
  ignore_paths:
    - "/admin/"
    - "/student/"
  css_selectors:
    - "a.researcher-link"
    - ".pagination a"

request_settings:
  delay: 2.0
  randomize_delay: true
  concurrent_requests: 1
  timeout: 30
  retries: 2

extract_fields:
  name:
    selector: "h1.researcher-name::text"
    transformations:
      - strip: true
      - title_case: true
    required: true

  email:
    selector: "a[href^='mailto:']::attr(href)"
    transformations:
      - replace:
          from: "mailto:"
          to: ""
      - lowercase: true
    required: true
    privacy:
      pseudonymise: "SHA256:8"

  research_interests:
    selector: ".research-tags li::text"
    transformations:
      - strip: true
      - limit: 5
      - join: "; "
    required: false

output:
  file: "./output/research-directory-{timestamp}.csv"

monitoring:
  log_file: "./logs/research-scraper-{timestamp}.log"
```

This configuration provides comprehensive control over ethical web scraping while maintaining compliance with privacy regulations and respectful crawling practices.
