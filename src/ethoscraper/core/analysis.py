#!/usr/bin/env python3
"""
LIA Analysis - Functional Approach
"""

import yaml
from openai import OpenAI
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import os
from dotenv import load_dotenv

# Load from your custom secrets file (relative to project root)
# Get the path relative to this script's location
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent.parent  # Go up from core/ to ethoscraper/ to src/ to project root
secrets_path = project_root / "secrets.env"
load_dotenv(secrets_path)


def load_compliance_data(compliance_path: Path) -> Dict:
    """Load and parse compliance.yaml file."""
    with open(compliance_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def extract_lia_data(compliance_data: Dict) -> Dict:
    """Extract LIA assessment data
      from compliance data."""
    lia_data = compliance_data.get('legitimate_interest_assessment', {})
    
    return {
        'purpose_test': lia_data.get('purpose_test', {}),
        'necessity_test': lia_data.get('necessity_test', {}),
        'balancing_test': lia_data.get('balancing_test', {}),
        'project_name': compliance_data.get('project_name', 'Unknown'),
        'target_url': compliance_data.get('target_url', 'Unknown'),
        'dpia_required': compliance_data.get('dpia_screening', {}).get('required', False)
    }


def create_analysis_prompt(lia_data: Dict) -> str:
    """Create the prompt for LLM analysis."""
    return f"""
You are an expert data protection analyst evaluating a Legitimate Interest Assessment (LIA) under GDPR Article 6(1)(f).
Remember that this LIA will be used to justify web scraping activities. All users will have no relationship with the data subjects, keep this in mind when evaluating the LIA.
If informing data subjects is a concern inform users that data controllers have 1 month from data collection to contact the data subject under GDPR Article 14 (3)(a)
It is okay to give a low confidence rating as accuracy is important, so err on the side of caution.

PROJECT: {lia_data['project_name']} | URL: {lia_data['target_url']}
DPIA Required: {lia_data['dpia_required']}

Purpose Test:
{yaml.dump(lia_data['purpose_test'], indent=2, default_flow_style=False)}

Necessity Test:
{yaml.dump(lia_data['necessity_test'], indent=2, default_flow_style=False)}

Balancing Test:
{yaml.dump(lia_data['balancing_test'], indent=2, default_flow_style=False)}

SCORING CRITERIA FOR CONSISTENCY:

Each test should be scored based on these specific factors:

PURPOSE TEST SCORING (0-100):
• 90-100: Purpose is specific, clearly articulated, legally sound with detailed justifications. Strong business/research rationale. Clear societal benefits identified.
• 70-89: Purpose is adequately defined with some legal justification. Business case present but may lack depth or specificity.
• 50-69: Purpose is vague or generic. Weak justification. Limited consideration of alternatives or benefits.
• 30-49: Purpose is unclear or potentially unlawful. Poor justification. Lacks business rationale.
• 0-29: Purpose is absent, incoherent, or clearly unlawful.

NECESSITY TEST SCORING (0-100):
• 90-100: Clear demonstration that processing is essential. Thorough analysis of alternatives. Proportionality well-established. Data minimization evident.
• 70-89: Processing necessity adequately justified. Some analysis of alternatives. Generally proportionate approach.
• 50-69: Necessity poorly justified. Limited consideration of alternatives. May be disproportionate to stated purpose.
• 30-49: Weak necessity argument. No real analysis of alternatives. Clearly disproportionate or excessive.
• 0-29: Processing is clearly unnecessary or alternatives not considered at all.

BALANCING TEST SCORING (0-100):
• 90-100: Comprehensive consideration of data subject rights. Strong safeguards in place. Clear understanding of expectations. Robust privacy measures.
• 70-89: Adequate consideration of rights. Some safeguards present. Generally understands expectations but may have gaps.
• 50-69: Limited consideration of rights. Weak safeguards. Poor understanding of individual expectations.
• 30-49: Minimal consideration of rights. No meaningful safeguards. Ignores individual expectations.
• 0-29: No consideration of data subject rights or expectations.

RED FLAG INDICATORS (automatically reduce scores):
- Answers under 20 words (shows lack of analysis)
- Generic responses like "no issues" or "no benefits"
- No mention of data subject rights or privacy considerations
- No consideration of alternatives or safeguards
- Vague purposes like "analysis" or "research" without specifics
- No acknowledgment of potential risks or ethical concerns

OVERALL CONFIDENCE RATING CALCULATION:
• Apply additional reductions for:
  - Insufficient detail in responses (-10 to -20 points)
  - Lack of legal awareness (-10 to -15 points)  
  - Missing key privacy considerations (-5 to -15 points)
  - Generic or dismissive answers (-5 to -20 points)

CONSISTENCY REQUIREMENTS:
1. If any individual test scores below 50, overall rating cannot exceed 60
2. If 2+ tests score below 60, overall rating cannot exceed 50  
3. Answers shorter than 15 words should be flagged as inadequate
4. "No" or "None" answers without explanation should be scored as poor
5. Missing consideration of data subject notification requirements should reduce scores

Your confidence_rating (0-100) should reflect the overall robustness of the LIA:
• 90-100: EXCELLENT - All three tests thoroughly documented and legally sound (average test scores 85+)
• 80-89:  GOOD - Most aspects well-covered with minor gaps (average test scores 70-84)  
• 70-79:  ACCEPTABLE - Basic requirements met with noticeable deficiencies (average test scores 60-69)
• 60-69:  CONCERNING - Significant gaps and weak justifications (average test scores 45-59)
• 50-59:  POOR - Major deficiencies across multiple areas (average test scores 30-44)
• 0-49:   INADEQUATE - Fundamental flaws in assessment (average test scores below 30)

Compliant/Low Risk = 80 - 100
Partially Compliant/Medium Risk = 60 - 79
Non-Compliant/High Risk = 0 - 59

REQUIRED OUTPUT FORMAT:

Return your analysis as a YAML document with the following structure:

```yaml
confidence_rating: <integer 0-100>
individual_test_scores:
  purpose_test: <integer 0-100>  
  necessity_test: <integer 0-100>
  balancing_test: <integer 0-100>
calculated_average: <float>
applied_reductions: <integer> # Total points deducted for issues
overall_assessment: "<brief summary of the LIA's compliance status>"
scoring_rationale: "<explanation of how the confidence rating was calculated>"
key_concerns:
  - "<specific concern 1>"
  - "<specific concern 2>"  
  - "..."
recommendations:
  - "<actionable recommendation 1>"
  - "<actionable recommendation 2>"
  - "..."
red_flags_identified:
  - "<red flag 1 if any>"
  - "<red flag 2 if any>"
section_analysis:
  purpose_test:
    score: <integer 0-100>
    scoring_justification: "<why this score was given>"
    strengths:
      - "<strength 1>"
      - "<strength 2>"
    weaknesses:
      - "<weakness 1>"
      - "<weakness 2>"
    comments: "<detailed analysis>"
  necessity_test:
    score: <integer 0-100>
    scoring_justification: "<why this score was given>"
    strengths:
      - "<strength 1>"
      - "<strength 2>"
    weaknesses:
      - "<weakness 1>"
      - "<weakness 2>"
    comments: "<detailed analysis>"
  balancing_test:
    score: <integer 0-100>
    scoring_justification: "<why this score was given>"
    strengths:
      - "<strength 1>"
      - "<strength 2>"
    weaknesses:
      - "<weakness 1>"
      - "<weakness 2>"
    comments: "<detailed analysis>" 
legal_risk_level: "<LOW|MEDIUM|HIGH>"
compliance_status: "<COMPLIANT|PARTIALLY_COMPLIANT|NON_COMPLIANT>"
```

Focus on providing specific, actionable insights based on GDPR requirements and data protection best practices.
Be especially critical of brief, generic, or dismissive responses that show lack of proper legal analysis.
"""


def analyze_with_llm(lia_data: Dict, api_key: str, model: str = "o3") -> Dict:
    """Analyze LIA data using OpenAI API with robust error handling."""
    client = OpenAI(api_key=api_key)
    prompt = create_analysis_prompt(lia_data)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a data protection expert. Always return properly formatted YAML with all required fields."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=20000
            )
            
            # Extract and parse YAML response with better error handling
            content = response.choices[0].message.content
            print(f"Debug - Raw LLM response length: {len(content)}")
            
            # Try multiple YAML extraction patterns
            yaml_content = None
            for pattern in ['```yaml\n', '```yaml', '```\n']:
                if pattern in content:
                    yaml_start = content.find(pattern) + len(pattern)
                    yaml_end = content.rfind('```')
                    if yaml_end > yaml_start:
                        yaml_content = content[yaml_start:yaml_end].strip()
                        break
            
            if not yaml_content:
                raise ValueError("Could not find YAML content in LLM response")
            
            print(f"Debug - Extracted YAML length: {len(yaml_content)}")
            
            # Parse YAML with error handling
            try:
                analysis = yaml.safe_load(yaml_content)
            except yaml.YAMLError as e:
                print(f"YAML parsing error: {e}")
                print(f"Problematic YAML content:\n{yaml_content}")
                raise ValueError(f"Invalid YAML format: {e}")
            
            # Validate required fields
            required_fields = ['confidence_rating', 'overall_assessment', 'legal_risk_level', 'compliance_status']
            missing_fields = [field for field in required_fields if field not in analysis]
            
            if missing_fields:
                print(f"Missing required fields: {missing_fields}")
                if attempt < max_retries - 1:
                    print(f"Retrying... (attempt {attempt + 1}/{max_retries})")
                    continue
                else:
                    # Provide default values for missing fields
                    defaults = {
                        'confidence_rating': 50,
                        'overall_assessment': 'Analysis incomplete due to parsing issues',
                        'legal_risk_level': 'MEDIUM',
                        'compliance_status': 'PARTIALLY_COMPLIANT',
                        'key_concerns': ['LLM response parsing issues'],
                        'recommendations': ['Review and complete assessment manually'],
                        'section_analysis': {
                            'purpose_test': {'score': 50, 'comments': 'Incomplete analysis'},
                            'necessity_test': {'score': 50, 'comments': 'Incomplete analysis'},
                            'balancing_test': {'score': 50, 'comments': 'Incomplete analysis'}
                        }
                    }
                    for field, default_value in defaults.items():
                        if field not in analysis:
                            analysis[field] = default_value
            
            return analysis
            
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                # Return a basic fallback analysis
                return {
                    'confidence_rating': 40,
                    'overall_assessment': f'Analysis failed due to technical issues: {e}',
                    'legal_risk_level': 'HIGH',
                    'compliance_status': 'NON_COMPLIANT',
                    'key_concerns': [f'Technical analysis failure: {e}'],
                    'recommendations': ['Manual review required due to technical issues'],
                    'section_analysis': {
                        'purpose_test': {'score': 40, 'comments': 'Technical analysis failure'},
                        'necessity_test': {'score': 40, 'comments': 'Technical analysis failure'},
                        'balancing_test': {'score': 40, 'comments': 'Technical analysis failure'}
                    }
                }


def generate_markdown_report(analysis: Dict, lia_data: Dict) -> str:
    """Generate comprehensive markdown report."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Helper function to format lists
    def format_list(items, prefix="- "):
        if not items:
            return f"{prefix}*No items reported*"
        return '\n'.join(f"{prefix}{item}" for item in items)
    
    # Helper function to format section analysis
    def format_section_analysis(section_name, section_data):
        if not section_data:
            return f"### {section_name}\n*No analysis data available*\n"
        
        score = section_data.get('score', 'N/A')
        strengths = section_data.get('strengths', [])
        weaknesses = section_data.get('weaknesses', [])
        comments = section_data.get('comments', '*No comments provided*')
        
        return f"""### {section_name}
**Score:** {score}/100

**Strengths:**
{format_list(strengths)}

**Weaknesses:**
{format_list(weaknesses)}

**Analysis:**
{comments}
"""

    # Determine risk badge
    risk_level = analysis.get('legal_risk_level', 'UNKNOWN')
    risk_badges = {
        'LOW': '🟢 **LOW RISK**',
        'MEDIUM': '🟡 **MEDIUM RISK**',
        'HIGH': '🔴 **HIGH RISK**'
    }
    risk_badge = risk_badges.get(risk_level, '⚪ **UNKNOWN RISK**')
    
    # Determine compliance badge
    compliance_status = analysis.get('compliance_status', 'UNKNOWN')
    compliance_badges = {
        'COMPLIANT': '✅ **COMPLIANT**',
        'PARTIALLY_COMPLIANT': '⚠️ **PARTIALLY COMPLIANT**',
        'NON_COMPLIANT': '❌ **NON-COMPLIANT**'
    }
    compliance_badge = compliance_badges.get(compliance_status, '❓ **UNKNOWN STATUS**')
    
    return f"""# Legitimate Interest Assessment Analysis Report

## Project Information
- **Project Name:** {lia_data['project_name']}
- **Target URL:** {lia_data['target_url']}
- **DPIA Required:** {'Yes' if lia_data['dpia_required'] else 'No'}
- **Analysis Date:** {timestamp}

## Executive Summary

| **Overall Confidence Rating** | **{analysis['confidence_rating']}/100** |
| **Legal Risk Level** | {risk_badge} |
| **Compliance Status** | {compliance_badge} |

### Overall Assessment
{analysis.get('overall_assessment', '*No overall assessment provided*')}

---

## Key Concerns

{format_list(analysis.get('key_concerns', []))}

---

## Recommendations

{format_list(analysis.get('recommendations', []))}

---

## Detailed Section Analysis

{format_section_analysis('Purpose Test', analysis.get('section_analysis', {}).get('purpose_test', {}))}

{format_section_analysis('Necessity Test', analysis.get('section_analysis', {}).get('necessity_test', {}))}

{format_section_analysis('Balancing Test', analysis.get('section_analysis', {}).get('balancing_test', {}))}

---

## Confidence Rating Scale

| Rating | Description |
|--------|-------------|
| 90-100 | **EXCELLENT** - All three tests thoroughly documented, legally sound, minimal legal risk |
| 80-89  | **GOOD** - Most aspects well-covered, minor gaps, generally compliant |
| 70-79  | **ACCEPTABLE** - Basic requirements met, some deficiencies, some legal risk |
| 60-69  | **CONCERNING** - Significant gaps, weak justifications, substantial legal risk |
| 50-59  | **POOR** - Major deficiencies, high legal risk, requires immediate attention, lack of justifications in general |
| 0-49   | **INADEQUATE** - Fundamental flaws, unacceptable legal risk, likely non-compliant, no justifications in general |

---

## Assessment Data Analyzed

### Purpose Test
```yaml
{yaml.dump(lia_data['purpose_test'], indent=2, default_flow_style=False)}
```

### Necessity Test
```yaml
{yaml.dump(lia_data['necessity_test'], indent=2, default_flow_style=False)}
```

### Balancing Test
```yaml
{yaml.dump(lia_data['balancing_test'], indent=2, default_flow_style=False)}
```

---

*Report generated by EthoScraper LIA Analysis Tool*
"""


def save_markdown_report(report: str, output_path: Path) -> None:
    """Save markdown report to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"✅ Analysis report saved to: {output_path}")


def analyze_compliance_file(compliance_path: Path, api_key: str, model: str = "gpt-4.1", output_path: Path = None) -> Tuple[Dict, str]:
    """Main analysis function - enhanced with markdown output."""
    compliance_data = load_compliance_data(compliance_path)
    lia_data = extract_lia_data(compliance_data)
    analysis = analyze_with_llm(lia_data, api_key, model)
    report = generate_markdown_report(analysis, lia_data)
    
    # Save to file if output path provided
    if output_path:
        save_markdown_report(report, output_path)
    
    return analysis, report


def main(model: str = None):
    """Main entry point for compliance analysis."""
    api_key = os.getenv('OPENAI_API_KEY')
    
    # Use provided model or environment variable, with gpt-4.1 as default fallback
    if model is None:
        model = os.getenv('MODEL_NAME', 'gpt-4.1')  # Changed default to gpt-4.1
    
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment")
        exit(1)
    
    # Use relative path from current working directory (assumes user starts from project folder)
    compliance_path = Path("output/compliance.yaml")
    
    # Generate timestamp for unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(f"output/lia_analysis_report_{timestamp}.md")
    
    print("🔍 Starting LIA Analysis...")
    print(f"📁 Input file: {compliance_path}")
    print(f"📄 Output file: {output_path}")
    print(f"🤖 Using model: {model}")
    print("-" * 50)
    
    try:
        analysis, report = analyze_compliance_file(compliance_path, api_key, model, output_path)
        
        # Display console summary
        print("\n📊 ANALYSIS SUMMARY:")
        print(f"   Confidence Rating: {analysis['confidence_rating']}/100")
        print(f"   Legal Risk Level: {analysis.get('legal_risk_level', 'Unknown')}")
        print(f"   Compliance Status: {analysis.get('compliance_status', 'Unknown')}")
        print(f"   Key Concerns: {len(analysis.get('key_concerns', []))}")
        print(f"   Recommendations: {len(analysis.get('recommendations', []))}")
        
        print(f"\n📝 Full detailed report saved to: {output_path}")
        print("✅ Analysis complete!")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        exit(1)


# Simple usage
if __name__ == "__main__":
    main()