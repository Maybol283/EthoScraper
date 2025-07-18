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

# Load from your custom secrets file
load_dotenv("secrets.env")


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

PROJECT: {lia_data['project_name']} | URL: {lia_data['target_url']}
DPIA Required: {lia_data['dpia_required']}

═══════════════════════════════════════════════════════════════════════════════════
ASSESSMENT DATA TO ANALYZE:
═══════════════════════════════════════════════════════════════════════════════════

Purpose Test:
{yaml.dump(lia_data['purpose_test'], indent=2, default_flow_style=False)}

Necessity Test:
{yaml.dump(lia_data['necessity_test'], indent=2, default_flow_style=False)}

Balancing Test:
{yaml.dump(lia_data['balancing_test'], indent=2, default_flow_style=False)}

═══════════════════════════════════════════════════════════════════════════════════
ANALYSIS INSTRUCTIONS:
═══════════════════════════════════════════════════════════════════════════════════

Please evaluate each component of the LIA according to GDPR standards:

1. PURPOSE TEST EVALUATION:
   - Is the legitimate interest clearly defined and specific?
   - Is the purpose lawful under applicable regulations?
   - Are there any competing legal bases that might be more appropriate?

2. NECESSITY TEST EVALUATION:
   - Is the data processing genuinely necessary for the stated purpose?
   - Are there less intrusive alternatives available?
   - Is the data collection proportionate to the intended outcome?

3. BALANCING TEST EVALUATION:
   - Are the data subject's rights and freedoms adequately considered?
   - Are there appropriate safeguards and protections in place?
   - Does the legitimate interest override the fundamental rights?

═══════════════════════════════════════════════════════════════════════════════════
CONFIDENCE RATING DEFINITIONS:
═══════════════════════════════════════════════════════════════════════════════════

Your confidence_rating (0-100) should reflect the overall robustness of the LIA:

• 90-100: EXCELLENT - All three tests are thoroughly documented, legally sound, 
          with clear justifications and appropriate safeguards. Minimal legal risk.

• 80-89:  GOOD - Most aspects well-covered, minor gaps in documentation or 
          safeguards. Generally compliant with manageable risk.

• 70-79:  ACCEPTABLE - Basic requirements met but with noticeable deficiencies 
          in one or more areas. Some legal risk present.

• 60-69:  CONCERNING - Significant gaps in analysis, weak justifications, or 
          inadequate safeguards. Substantial legal risk.

• 50-59:  POOR - Major deficiencies across multiple areas. High legal risk, 
          requires immediate attention.

• 0-49:   INADEQUATE - Fundamental flaws in the assessment. Unacceptable legal 
          risk, likely non-compliant with GDPR.

═══════════════════════════════════════════════════════════════════════════════════
REQUIRED OUTPUT FORMAT:
═══════════════════════════════════════════════════════════════════════════════════

Return your analysis as a YAML document with the following structure:

```yaml
confidence_rating: <integer 0-100>
overall_assessment: "<brief summary of the LIA's compliance status>"
key_concerns:
  - "<specific concern 1>"
  - "<specific concern 2>"
  - "..."
recommendations:
  - "<actionable recommendation 1>"
  - "<actionable recommendation 2>"
  - "..."
section_analysis:
  purpose_test:
    score: <integer 0-100>
    strengths:
      - "<strength 1>"
      - "<strength 2>"
    weaknesses:
      - "<weakness 1>"
      - "<weakness 2>"
    comments: "<detailed analysis>"
  necessity_test:
    score: <integer 0-100>
    strengths:
      - "<strength 1>"
      - "<strength 2>"
    weaknesses:
      - "<weakness 1>"
      - "<weakness 2>"
    comments: "<detailed analysis>"
  balancing_test:
    score: <integer 0-100>
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
"""


def analyze_with_llm(lia_data: Dict, api_key: str, model: str = "gpt-4") -> Dict:
    """Analyze LIA data using OpenAI API."""
    client = OpenAI(api_key=api_key)
    prompt = create_analysis_prompt(lia_data)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a data protection expert."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=2000
    )
    
    # Extract and parse YAML response
    content = response.choices[0].message.content
    yaml_start = content.find('```yaml\n') + 8
    yaml_end = content.rfind('```')
    yaml_content = content[yaml_start:yaml_end]
    
    return yaml.safe_load(yaml_content)


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

| Metric | Value |
|--------|-------|
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
| 50-59  | **POOR** - Major deficiencies, high legal risk, requires immediate attention |
| 0-49   | **INADEQUATE** - Fundamental flaws, unacceptable legal risk, likely non-compliant |

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


def analyze_compliance_file(compliance_path: Path, api_key: str, model: str = "gpt-4", output_path: Path = None) -> Tuple[Dict, str]:
    """Main analysis function - enhanced with markdown output."""
    compliance_data = load_compliance_data(compliance_path)
    lia_data = extract_lia_data(compliance_data)
    analysis = analyze_with_llm(lia_data, api_key, model)
    report = generate_markdown_report(analysis, lia_data)
    
    # Save to file if output path provided
    if output_path:
        save_markdown_report(report, output_path)
    
    return analysis, report


# Simple usage
if __name__ == "__main__":
    api_key = os.getenv('OPENAI_API_KEY')
    model = os.getenv('MODEL_NAME', 'gpt-4')  # Default fallback
    
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment")
        exit(1)
    
    compliance_path = Path("Test/output/compliance.yaml")
    
    # Generate timestamp for unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(f"Test/output/lia_analysis_report_{timestamp}.md")
    
    print("🔍 Starting LIA Analysis...")
    print(f"📁 Input file: {compliance_path}")
    print(f"📄 Output file: {output_path}")
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