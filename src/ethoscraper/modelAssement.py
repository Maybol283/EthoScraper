#!/usr/bin/env python3
"""
LIA Analysis - Functional Approach
"""

import yaml
import json
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
You are an expert data protection analyst evaluating a Legitimate Interest Assessment (LIA).

PROJECT: {lia_data['project_name']} | URL: {lia_data['target_url']}

RESPONSES:
Purpose Test: {json.dumps(lia_data['purpose_test'], indent=2)}
Necessity Test: {json.dumps(lia_data['necessity_test'], indent=2)}
Balancing Test: {json.dumps(lia_data['balancing_test'], indent=2)}

Return JSON with: confidence_rating (0-100), key_concerns[], recommendations[], section_analysis{{}}
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
    
    # Extract and parse JSON response
    content = response.choices[0].message.content
    json_start = content.find('{')
    json_end = content.rfind('}') + 1
    
    return json.loads(content[json_start:json_end])


def generate_report(analysis: Dict, lia_data: Dict) -> str:
    """Generate formatted report."""
    return f"""
╔════════════════════════════════════════════════════════════════════════════════╗
║                          LIA ANALYSIS REPORT                                   ║
╠════════════════════════════════════════════════════════════════════════════════╣
║ Project: {lia_data['project_name']:<65}                                        ║
║ Confidence: {analysis['confidence_rating']:>3}%                                ║
╚════════════════════════════════════════════════════════════════════════════════╝

⚠️  KEY CONCERNS:
{chr(10).join(f'   • {concern}' for concern in analysis.get('key_concerns', []))}

💡 RECOMMENDATIONS:
{chr(10).join(f'   • {rec}' for rec in analysis.get('recommendations', []))}
"""


def analyze_compliance_file(compliance_path: Path, api_key: str, model: str = "gpt-4") -> Tuple[Dict, str]:
    """Main analysis function - simple pipeline."""
    compliance_data = load_compliance_data(compliance_path)
    lia_data = extract_lia_data(compliance_data)
    analysis = analyze_with_llm(lia_data, api_key, model)
    report = generate_report(analysis, lia_data)
    
    return analysis, report


# Simple usage
if __name__ == "__main__":
    api_key = os.getenv('OPENAI_API_KEY')
    model = os.getenv('MODEL_NAME', 'gpt-4')  # Default fallback
    
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment")
        exit(1)
    
    compliance_path = Path("Test/output/compliance.yaml")
    analysis, report = analyze_compliance_file(compliance_path, api_key, model)
    print(report)