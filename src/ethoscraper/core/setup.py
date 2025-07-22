#!/usr/bin/env python3
"""ethoscraper.setup

A tiny helper script that asks the user for a project name and creates a
folder with that name in the current working directory.

Usage (from repo root):
    poetry run python -m ethoscraper.setup
or directly:
    python src/ethoscraper/setup.py
"""

from pathlib import Path
import shutil
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import urllib.error
import ssl
import yaml
from datetime import datetime
import time

# ──────────────────────────────────────────────────────────────────────────────
# URL and robots.txt utilities
# ──────────────────────────────────────────────────────────────────────────────

def normalize_url(raw: str, default_scheme: str = "https") -> str:
    """Add https:// if no scheme is provided."""
    if "://" not in raw:
        raw = f"{default_scheme}://{raw}"
    return raw


def fetch_and_display_robots(target_url: str, ua: str = "*") -> dict:
    """Fetch robots.txt, display summary, and return parsed info."""
    start_url = normalize_url(target_url)
    parsed = urlparse(start_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    rp = RobotFileParser()
    rp.set_url(robots_url)

    try:
        rp.read()
        fetched = True
    except (urllib.error.HTTPError, urllib.error.URLError, ssl.SSLError) as exc:
        return {
            "start_url": start_url,
            "robots_url": robots_url,
            "fetched": False,
            "error": f"{type(exc).__name__}: {exc.reason}",
        }

    summary = {
        "start_url": start_url,
        "robots_url": robots_url,
        "fetched": True,
        "allows_root": rp.can_fetch(ua, "/"),
        "crawl_delay": rp.crawl_delay(ua),
        "sitemaps": rp.site_maps() or [],
        "error": None,
    }

    # Display formatted summary
    tick = lambda b: "✅" if b else "❌"
    lines = [
        "",
        "┏━━━━━━━━━━━━ robots.txt ━━━━━━━━━━━━┓",
        f" URL          : {summary['robots_url']}",
        f" Allows '/'   : {tick(summary['allows_root'])}",
        f" Crawl-delay  : {summary['crawl_delay'] or '—'}",
        f" Sitemaps     : {', '.join(summary['sitemaps']) or '—'}",
        "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛",
        "",
    ]
    print("\n".join(lines))
    
    # Give user time to read robots.txt info
    input("Press Enter to continue...")
    print()
    
    return summary


# ──────────────────────────────────────────────────────────────────────────────
# Project structure creation
# ──────────────────────────────────────────────────────────────────────────────

def create_project_structure(project_name: str) -> tuple[Path, Path]:
    """Create project directory and output subdirectory."""
    target_dir = Path(project_name)
    
    if target_dir.exists():
        print(f"Directory '{target_dir}' already exists. Aborting.")
        raise FileExistsError(f"Directory '{target_dir}' already exists")
    
    try:
        target_dir.mkdir(parents=True, exist_ok=False)
        print(f"Created directory: {target_dir.resolve()}")
    except FileExistsError:
        print(f"Directory '{target_dir}' already exists. Aborting.")
        raise
    
    # Create output subdirectory for CSV files
    output_dir = target_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created output directory: {output_dir}")
    
    return target_dir, output_dir


def copy_and_customize_templates(target_dir: Path, output_dir: Path, project_name: str, target_url: str) -> None:
    """Copy template files and customize them with project-specific values."""
    for name in ("compliance-template.yaml", "target-template.yaml"):
        src = Path(__file__).parent.parent / "templates" / name
        
        # compliance.yaml goes to output/, target.yaml stays in project root
        if name == "compliance-template.yaml":
            dst = output_dir / name.replace("-template", "")
        else:
            dst = target_dir / name.replace("-template", "")
        
        try:
            shutil.copy(src, dst)
            
            # Customize content with project values
            content = dst.read_text(encoding="utf-8")
            
            if dst.name == "compliance.yaml":
                content = content.replace(
                    'target_url: "https://university.example.edu/department/computer-science/people"',
                    f'target_url: "{target_url}"'
                )
                content = content.replace(
                    'project_name: "uni-staff-directory-2025"',
                    f'project_name: "{project_name}"'
                )
                content = content.replace(
                    'report_timestamp: "2025-06-13T10:51:21Z"',
                    f'report_timestamp: "{datetime.now().isoformat()}"'
                )
            elif dst.name == "target.yaml":
                content = content.replace(
                    '- "https://university.example.edu/department/computer-science/people"',
                    f'- "{target_url}"'
                )
                content = content.replace(
                    'job_name: "uni-staff-directory-2025"',
                    f'job_name: "{project_name}"'
                )
            
            dst.write_text(content, encoding="utf-8")
            
        except FileExistsError:
            print(f"File '{dst.name}' already exists. Skipping.")


# ──────────────────────────────────────────────────────────────────────────────
# User interaction
# ──────────────────────────────────────────────────────────────────────────────

def get_user_inputs() -> tuple[str, str]:
    """Prompt user for project name and target URL."""
    
    project_name = input("Enter a project name: ").strip()
    while not project_name:
        project_name = input("Project name cannot be empty. Try again: ").strip()
    
    print()
    target_url = input("What is the base url of the website you want to scrape (e.g. example.com): ").strip()
    while not target_url:
        target_url = input("Target url cannot be empty. Try again: ").strip()
    
    return project_name, target_url


def confirm_proceed() -> bool:
    """Ask user to confirm they want to proceed with the project."""
    confirmed = input("Can you confirm that you wish to proceed with the project? (y/n): ").strip().lower()
    while confirmed not in ("y", "n"):
        confirmed = input("Please enter 'y' or 'n': ").strip().lower()
    return confirmed == "y"
# ──────────────────────────────────────────────────────────────────────────────
# YAML Helper Functions
# ──────────────────────────────────────────────────────────────────────────────

def _write_to_compliance_yaml(compliance_path: Path, section_path: str, data: dict) -> None:
    """
    Write data to a specific section in the compliance.yaml file.
    
    Args:
        compliance_path: Path to the compliance.yaml file
        section_path: Dot-separated path to the section (e.g., "legitimate_interest_assessment.purpose_test")
        data: Dictionary of data to write to that section
    """
    # Load existing YAML
    try:
        with open(compliance_path, 'r', encoding='utf-8') as f:
            compliance_data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Warning: {compliance_path} not found. Cannot write answers to compliance file.")
        return
    except Exception as e:
        print(f"Error reading {compliance_path}: {e}")
        return
    
    # Navigate to the correct section
    current_section = compliance_data
    path_parts = section_path.split('.')
    
    # Navigate to the parent section
    for part in path_parts[:-1]:
        if part not in current_section:
            current_section[part] = {}
        current_section = current_section[part]
    
    # Set the final section
    final_key = path_parts[-1]
    if final_key not in current_section:
        current_section[final_key] = {}
    
    # Create sections using keys as names
    for key, value in data.items():
        current_section[final_key][key] = value
    
    # Write back to file
    try:
        with open(compliance_path, 'w', encoding='utf-8') as f:
            yaml.dump(compliance_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    except Exception as e:
        print(f"Error writing to {compliance_path}: {e}")


# ──────────────────────────────────────────────────────────────────────────────
# Data Protection Impact Assessment
# ──────────────────────────────────────────────────────────────────────────────
def dpia_screening() -> tuple[bool, list[str]]:
    """
    Ask the nine WP29 high-risk criteria.
    Returns (dpiA_required, criteria_flagged)
    """
    print("=== DPIA SCREENING CHECK ===\n"
          "Answer Y/N.\n If you answer 'Yes' to:\n"
          "  • Automated-decision making with legal effect, or\n"
          "  • Systematic monitoring of public space,\n"
          "a DPIA is always required.\n"
          "Otherwise, two or more Yes answers also trigger a DPIA.\n")
    time.sleep(5)
    print("Are you ready to proceed? (y/n): ")
    proceed = input().strip().lower()
    if proceed == "n":
        print("Please run the DPIA screening again when you are ready.")
        return False, []
    
    criteria = {
        "evaluation_scoring":      "1. Evaluation or scoring / profiling?",
        "automated_decisions":     "2. Automated decisions with legal or similarly significant effect?",
        "systematic_monitoring":   "3. Systematic monitoring of a publicly accessible area?",
        "sensitive_or_special":    "4. Processing special-category, criminal-offence or highly personal data?",
        "large_scale":             "5. Processing on a large scale?",
        "matching_combining":      "6. Matching or combining datasets from different sources?",
        "vulnerable_subjects":     "7. Data about vulnerable subjects (children, employees, asylum-seekers…)?",
        "innovative_use":          "8. Innovative technology or novel processing techniques?",
        "rights_prevention":       "9. Processing that prevents people exercising a right or accessing a service?"
    }

    # NEW: illustrative examples for each criterion
    examples = {
        "evaluation_scoring": [
            " Building credit-scores from banking and salary data.",
            " Predicting health risks from consumer DNA tests."
        ],
        "automated_decisions": [
            " Auto-approving or rejecting loan applications with no human review."
        ],
        "systematic_monitoring": [
            " Continuous CCTV + face recognition in a shopping mall."
        ],
        "sensitive_or_special": [
            " Hospital storing patient medical records (health data)."
        ],
        "large_scale": [
            " Tracking location data from millions of mobile devices for six months."
        ],
        "matching_combining": [
            " Combining loyalty-card data with social-media profiles to build",
            " detailed marketing segments."
        ],
        "vulnerable_subjects": [
            " Collecting classroom attendance records of children."
        ],
        "innovative_use": [
            " Using an experimental AI model to predict employee attrition from",
            " email sentiment."
        ],
        "rights_prevention": [
            " Screening customers against a credit database to decide if they may",
            " open a bank account."
        ],
    }

    flagged: list[str] = []
    for key, prompt in criteria.items():
        # ---- EXAMPLE block ----
        print("\nEXAMPLE:")
        for line in examples[key]:
            print(line)
        print()  # blank line before the actual question
        # -----------------------
        ans = input(f"{prompt} (Y/N): ").strip().lower()
        if ans in ("y", "yes"):
            flagged.append(key)

    # Hard triggers per Art 35(3)
    hard_triggers = {"automated_decisions", "systematic_monitoring"}

    needs_dpia = (
        bool(hard_triggers & set(flagged))      # any hard trigger
        or len(flagged) >= 2                    # or two-criteria rule
    )
    
    print(f"\n✅ DPIA screening questions complete!")
    print(f"Flagged criteria: {len(flagged)} out of 9")
    if flagged:
        print(f"Flagged areas: {', '.join(flagged)}")
    
    input("Press Enter to see the DPIA assessment result...")

    return needs_dpia, flagged
# ──────────────────────────────────────────────────────────────────────────────
# Legitimate Interest Assessment
# ──────────────────────────────────────────────────────────────────────────────

def purpose_test(target_url: str, compliance_path: Path) -> list[str]:
    """Test if the purpose of the project is legitimate."""
    print(f"=== PURPOSE TEST ===")
    print(f"Testing if the purpose of the project is legitimate for {target_url}")
    print("\nThis test examines whether your purposes are legitimate and lawful.")
    print("You'll be asked 7 questions with examples provided for each.\n")
    
    input("Press Enter when ready to begin the Purpose Test...")
    print()
    
    # Purpose test questions - unified structure
    purpose_data = {
        "purpose_why": {
            "question": "1. Why are you scraping this website?",
            "yaml_key": "why_scraping",
            "examples": [
                " To analyse trends in how UK residents discuss local",
                " air-quality measures on publicly available newspaper",
                " comment sections and community forums."
            ]
        },
        "benefit_org": {
            "question": "2. Benefit to our organisation?",
            "yaml_key": "benefit_to_organisation",
            "examples": [
                " Peer-reviewed publications and REF impact case-study;",
                " Evidence base for grant applications on urban pollution",
                " mitigation."
            ]
        },
        "third_party": {
            "question": "3. Third-party benefits?",
            "yaml_key": "third_party_benefits",
            "examples": [
                " Local authorities and campaign groups gain anonymised",
                " insights into public sentiment for policy design."
            ]
        },
        "public_benefit": {
            "question": "4. Wider public/societal benefits?",
            "yaml_key": "public_societal_benefits",
            "examples": [
                " Better-targeted public-health messaging and",
                " environmental interventions."
            ]
        },
        "no_process": {
            "question": "5. What would happen if we couldn't process this data?",
            "yaml_key": "if_couldnt_process",
            "examples": [
                " We would rely on expensive, limited survey panels,",
                " missing authentic grassroots discourse."
            ]
        },
        "positive_outcome": {
            "question": "6. Are there any positive outcomes for individuals involved in the processing?",
            "yaml_key": "positive_outcome_individuals",
            "examples": [
                " Voices expressed in small regional outlets are surfaced",
                " to policy-makers, potentially improving neighbourhood",
                " air quality."
            ]
        },
        "ethical_issues": {
            "question": "7. Are there any ethical issues with the processing?",
            "yaml_key": "ethical_issues",
            "examples": [
                " Risk of re-identifying individuals from small forums.",
                " Mitigated by aggregating data, removing usernames, and",
                " focusing on themes rather than individual opinions."
            ]
        }
    }
    
    answers = []
    collected_answers = {}
    
    for key, data in purpose_data.items():
        print("\nEXAMPLE:")
        for line in data["examples"]:
            print(line)
        print()
        answer = input(f"{data['question']} ").strip()
        while len(answer) < 10:
            print("Answer must be at least 10 characters long. Please provide a more detailed response.")
            answer = input(f"{data['question']} ").strip()
        answers.append(answer)
        collected_answers[data["yaml_key"]] = answer
    
    # Write answers to compliance.yaml
    _write_to_compliance_yaml(compliance_path, "legitimate_interest_assessment.purpose_test", collected_answers)
    
    print(f"✅ Purpose Test complete! All answers have been recorded and written to compliance.yaml")
    input("Press Enter to finish the Purpose Test...")
    return answers

def necessity_test(target_url: str, compliance_path: Path) -> list[str]:
    """Test if the data processing is necessary and proportionate."""
    print(f"=== NECESSITY TEST ===")
    print(f"Testing if the data processing is necessary for {target_url}")
    print("\nThis test examines whether the processing is necessary to achieve your purpose")
    print("and whether you could achieve the same result in a less intrusive way.")
    print("You'll be asked 4 key questions with examples.\n")
    
    input("Press Enter when ready to begin the Necessity Test...")
    print()
    
    # Necessity test questions - unified structure
    necessity_data = {
        "helps_achieve": {
            "question": "1. Will the processing actually help you achieve your purpose?",
            "yaml_key": "will_processing_help_achieve_purpose",
            "examples": [
                " Yes, analysing public discourse requires processing the text",
                " content and associated metadata to identify themes and",
                " geographical patterns in air quality discussions."
            ]
        },
        "proportionate": {
            "question": "2. Is the processing proportionate to that purpose?",
            "yaml_key": "is_processing_proportionate",
            "examples": [
                " The processing is proportionate - we only collect publicly",
                " available comments and aggregate them for thematic analysis,",
                " not individual profiling or intrusive monitoring."
            ]
        },
        "achieve_without": {
            "question": "3. Can you achieve your purpose without processing the data, or by processing less data?",
            "yaml_key": "can_achieve_without_processing",
            "examples": [
                " No, we cannot achieve meaningful trend analysis without",
                " processing the text data. However, we limit collection to",
                " relevant discussion threads only."
            ]
        },
        "less_intrusive": {
            "question": "4. Can you achieve your purpose by processing the data in another more obvious or less intrusive way?",
            "yaml_key": "can_achieve_less_intrusively",
            "examples": [
                " Alternative approaches like surveys would be less",
                " representative and more intrusive. Public forum analysis",
                " is the least invasive method for this research question."
            ]
        }
    }
    
    answers = []
    collected_answers = {}
    
    for key, data in necessity_data.items():
        print("\nEXAMPLE:")
        for line in data["examples"]:
            print(line)
        print()
        answer = input(f"{data['question']} ")
        answers.append(answer)
        collected_answers[data["yaml_key"]] = answer
    
    # Write answers to compliance.yaml
    _write_to_compliance_yaml(compliance_path, "legitimate_interest_assessment.necessity_test", collected_answers)
    
    print(f"✅ Necessity Test complete! All answers have been recorded and written to compliance.yaml")
    input("Press Enter to finish the Necessity Test...")
    return answers

def balance_test(target_url: str, compliance_path: Path) -> list[str]:
    """Test if the data processing is balanced."""
    print(f"=== BALANCING TEST ===")
    print(f"Testing if the data processing is balanced for {target_url}")
    print("\nThis test weighs your legitimate interests against the individuals' interests,")
    print("fundamental rights and freedoms. It has two main sections:")
    print("1. Nature of the Data - What type of data are you processing?")
    print("2. Reasonable Expectations - What would individuals reasonably expect?\n")
    
    input("Press Enter when ready to begin the Balancing Test...")
    print()
    
    print("=== NATURE OF THE DATA ===\n")
    print("First, let's examine the nature of the data you're processing.")
    print("Please answer with Yes (Y) or No (N)\n")
    
    input("Press Enter to continue with the Nature of Data questions...")
    print()
    
    # Nature of Data questions - unified structure
    nature_data = {
        "special_category": {
            "question": "1. Are you processing special category data (racial/ethnic origin, political opinions, religious/philosophical beliefs, \n trade union membership, genetic data, biometric data, health data, sex life, sexual orientation)?",
            "yaml_key": "processing_special_category_data",
            "examples": None,
            "followup_examples": [
                " We are processing health data from patient medical records that include",
                " diagnoses, treatment histories, and genetic test results for individuals",
                " participating in a clinical research study."
            ]
        },
        "criminal_data": {
            "question": "2. Are you processing criminal offence data (personal data relating to criminal convictions and offences or related security measures)?",
            "yaml_key": "processing_criminal_data",
            "examples": None,
            "followup_examples": [
                " We are processing conviction data from court records. Data includes conviction",
                " dates, offence types, and sentencing outcomes from publicly",
                " available court databases."
            ]
        },
        "private_data": {
            "question": "3. Are you processing particularly 'private' data (financial, intimate personal details)?",
            "yaml_key": "processing_private_data",
            "examples": None,
            "followup_examples": [
                " We are processing financial transaction data from bank",
                " statements. Data includes",
                " transaction amounts, merchant categories, and spending",
                " patterns from anonymized customer records."
            ]
        },
        "vulnerable_data": {
            "question": "4. Are you processing children's data or data from vulnerable individuals?",
            "yaml_key": "processing_vulnerable_data",
            "examples": None,
            "followup_examples": [
                " We are processing educational records of children aged 13-16",
                " Data includes test scores,",
                " attendance records, and demographic information with parental",
                " consent and school ethics approval."
            ]
        },
        "personal_or_professional": {
            "question": "5. Is the data about people in their personal or professional capacity?",
            "yaml_key": "data_personal_or_professional_capacity",
            "examples": [
                " Mixed - some comments may be from individuals in personal",
                " capacity (residents discussing local air quality) and some",
                " in professional capacity (officials, experts)."
            ],
            "followup_examples": [
                " The data includes both personal capacity individuals (local residents",
                " discussing environmental concerns in their neighborhoods) and professional",
                " capacity individuals (environmental officials, scientists, policy makers)."
            ]
        }
    }
    
    nature_answers = []
    collected_answers = {}
    
    for key, data in nature_data.items():
        # Show examples if available
        if data["examples"]:
            print("\nEXAMPLE:")
            for line in data["examples"]:
                print(line)
            print()
        
        initial_answer = input(f"{data['question']} ")
        
        # Always ask for expansion when someone answers yes
        if initial_answer in ["Y", "Yes", "y", "yes"]:
            print("\nEXAMPLE:")
            for line in data["followup_examples"]:
                print(line)
            print()
            detailed_answer = input(f"Please describe the affected group and specify what type of {key.replace('_', ' ')} you are processing: ").strip()
            while len(detailed_answer) < 10:
                print("Answer must be at least 10 characters long. Please provide a more detailed response.")
                detailed_answer = input(f"Please describe the affected group and specify what type of {key.replace('_', ' ')} you are processing: ").strip()
            final_answer = detailed_answer
        else:
            final_answer = "No" if initial_answer in ["N", "No", "n", "no"] else initial_answer
        
        nature_answers.append(final_answer)
        collected_answers[data["yaml_key"]] = final_answer
    
    # Reasonable Expectations section
    print("\n=== REASONABLE EXPECTATIONS ===\n")
    print("Now let's examine what individuals would reasonably expect.")
    print("This section looks at the relationship you have with individuals,")
    print("how the data was collected, and what they were told.")
    print("Please provide detailed answers.\n")
    
    input("Press Enter to continue with the Reasonable Expectations questions...")
    print()
    
    # Reasonable Expectations questions - unified structure
    expectations_data = {
        "told_individuals": {
            "question": "1. What did you tell individuals at the time of collection or when will they be informed and what will you tell them?",
            "yaml_key": "what_told_individuals_at_collection",
            "examples": [
                " Not applicable - we did not collect data directly from",
                " individuals. The data comes from public forums and",
                " newspaper comment sections."
            ]
        },
        "third_party_told": {
            "question": "2. If obtained from third party, what did they tell individuals about reuse by third parties?",
            "yaml_key": "third_party_disclosure_about_reuse",
            "examples": [
                " The website terms of service typically state that comments",
                " may be used for research purposes or by third parties.",
                " Forum policies generally allow academic research use."
            ]
        },
        "obvious_purpose": {
            "question": "3. Is your intended purpose and method obvious or widely understood by your data subjects?",
            "yaml_key": "purpose_and_method_obvious_or_understood",
            "examples": [
                " Academic research on public environmental discourse is",
                " widely understood and accepted. The purpose of analyzing",
                " public sentiment on air quality is straightforward."
            ]
        },
        "innovative_processing": {
            "question": "4. Are you doing anything new or innovative with the data?",
            "yaml_key": "using_innovative_processing_methods",
            "examples": [
                " The research methods are standard (thematic analysis",
                " of public comments). We are not using novel AI techniques",
                " or innovative processing methods."
            ]
        },
        "evidence_expectations": {
            "question": "5. Do you have evidence about expectations (market research, focus groups, consultation)?",
            "yaml_key": "evidence_about_individual_expectations",
            "examples": [
                " We conducted focus groups with 20 local residents who",
                " confirmed they expect their public environmental comments",
                " to be used for legitimate academic research."
            ]
        },
        "other_factors": {
            "question": "6. Are there other factors that would affect whether individuals expect this processing?",
            "yaml_key": "other_factors_affecting_expectations",
            "examples": [
                " The data subjects have chosen to post in public forums",
                " about environmental issues, suggesting they expect public",
                " visibility and potential research use of their comments."
            ]
        }
    }
    
    expectations_answers = []
    for key, data in expectations_data.items():
        print("\nEXAMPLE:")
        for line in data["examples"]:
            print(line)
        print()
        answer = input(f"{data['question']} ").strip()
        while len(answer) < 10:
            print("Answer must be at least 10 characters long. Please provide a more detailed response.")
            answer = input(f"{data['question']} ").strip()
        expectations_answers.append(answer)
        collected_answers[data["yaml_key"]] = answer
    
    # Write answers to compliance.yaml
    _write_to_compliance_yaml(compliance_path, "legitimate_interest_assessment.balancing_test", collected_answers)
    
    print(f"✅ Balancing Test complete! All answers have been recorded and written to compliance.yaml")
    input("Press Enter to finish the Balancing Test...")
    return nature_answers + expectations_answers

# ──────────────────────────────────────────────────────────────────────────────
# LIA Wizard
# ──────────────────────────────────────────────────────────────────────────────

def run_lia_wizard(project_dir: Path, target_url: str) -> None:
    """
    Run the complete Legitimate Interest Assessment wizard.
    
    Args:
        project_dir: Path to the project directory
        target_url: The target URL being assessed
    """
    compliance_path = project_dir / "output" / "compliance.yaml"
    
    if not compliance_path.exists():
        print(f"Error: compliance.yaml not found at {compliance_path}")
        print("Please run the project setup first.")
        return
    
    # Run DPIA screening first
    print("First,let's check if a DPIA (Data Protection Impact Assessment) is required...\n")
    dpia_required, flagged_criteria = dpia_screening()
    
    # Write DPIA results to compliance.yaml
    dpia_data = {
        "required": dpia_required,
        "flagged_criteria": flagged_criteria
    }
    _write_to_compliance_yaml(compliance_path, "dpia_screening", dpia_data)
    
    if dpia_required:
        print(f"\n❌ DPIA is REQUIRED based on the flagged criteria: {', '.join(flagged_criteria)}")
        print("=" * 70)
        print("🛑 PROJECT SETUP TERMINATED")
        print("=" * 70)
        print("\n❗ IMPORTANT: You MUST conduct a full Data Protection Impact Assessment (DPIA)")
        print("   before proceeding with any data processing activities.\n")
        print("📋 DPIA results have been recorded in compliance.yaml")
        print(f"   File location: {compliance_path}")
        print("\n📚 For guidance on conducting a DPIA, refer to:")
        print("   • GDPR Articles 35-36")
        print("   • ICO DPIA guidance: https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/accountability-and-governance/data-protection-impact-assessments-dpias/")
        print("   • EU GDPR guide: https://gdpr.eu/data-protection-impact-assessment-template/")
        print("\n⚠️  Do not proceed with scraping until you have:")
        print("   1. Completed a full DPIA")
        print("   2. Implemented necessary safeguards")
        print("   3. Obtained any required approvals")
        print("\n🔄 You may re-run this setup after completing your DPIA.")
        print("=" * 70)
        return  # Terminate program - no LIA wizard
    else:
        print(f"\n✅ DPIA is not required based on current assessment.\n")
        input("Press Enter to continue with the LIA assessment...")
    
    # Continue with LIA tests
    print("Now proceeding with the Legitimate Interest Assessment...\n")
    print("\n\n=== LEGITIMATE INTEREST ASSESSMENT WIZARD ===\n")
    print("This wizard will guide you through the three main tests:")
    print("1. Purpose Test - Is your purpose legitimate?")
    print("2. Necessity Test - Is processing necessary?")
    print("3. Balancing Test - Do your interests override individuals' rights?\n")
    
    print("Are you ready to proceed? (y/n): ")
    proceed = input().strip().lower()
    if proceed == "n":
        print("Setup incomplete. Please rerun the wizard when you are ready.")
        return
    
    # Initialize the LIA structure with empty subsections
    lia_structure = {
        "purpose_test": {},
        "necessity_test": {},
        "balancing_test": {}
    }
    _write_to_compliance_yaml(compliance_path, "legitimate_interest_assessment", lia_structure)
    
    # Run the three tests
    print("=" * 50)
    purpose_test(target_url, compliance_path)
    
    print("\n" + "=" * 50)
    print("Moving to the next test...")
    input("Press Enter to continue to the Necessity Test...")
    print()
    necessity_test(target_url, compliance_path)
    
    print("\n" + "=" * 50)
    print("Moving to the final test...")
    input("Press Enter to continue to the Balancing Test...")
    print()
    balance_test(target_url, compliance_path)
    
    # Final assessment
    print("\n" + "=" * 50)
    print("=== LIA ASSESSMENT COMPLETE ===")
    print(f"All answers have been written to: {compliance_path}")
    print("\nPlease review the compliance.yaml file and make any necessary adjustments.")
    print("You may now proceed with your data processing activities.")
    
    input("\nPress Enter to finish the LIA wizard...")


# ──────────────────────────────────────────────────────────────────────────────
# Main orchestration
# ──────────────────────────────────────────────────────────────────────────────

def run_wizard_for_existing_project() -> None:
    """Run the LIA wizard for an existing project in the current directory."""
    # Look for target.yaml to get project info
    target_yaml_path = Path("target.yaml")
    if not target_yaml_path.exists():
        print("Error: target.yaml not found in current directory.")
        print("Please run this from a project directory or run the main setup first.")
        return
    
    try:
        with open(target_yaml_path, 'r', encoding='utf-8') as f:
            target_data = yaml.safe_load(f)
        
        # Extract target URL from the first URL in the list
        target_urls = target_data.get('target_urls', [])
        if not target_urls:
            print("Error: No target URLs found in target.yaml")
            return
        
        target_url = target_urls[0]  # Use the first URL
        project_dir = Path(".")
        
        print(f"Running LIA wizard for project in: {project_dir.resolve()}")
        print(f"Target URL: {target_url}\n")
        
        run_lia_wizard(project_dir, target_url)
        
    except Exception as e:
        print(f"Error reading target.yaml: {e}")
        return


def main() -> None:  # pragma: no cover
    """Main setup workflow orchestration."""
    import sys
    
    # Check if user wants to run the LIA wizard directly
    if len(sys.argv) > 1 and sys.argv[1] == "--lia-wizard":
        run_wizard_for_existing_project()
        return
    
    try:
        # Get user inputs
        project_name, target_url = get_user_inputs()
        
        # Fetch and display robots.txt info
        robots_summary = fetch_and_display_robots(target_url)
        target_url = robots_summary["start_url"]  # Use normalized URL
        
        # Confirm user wants to proceed
        if not confirm_proceed():
            print("Closing the project setup...")
            return
        
        # Create project structure
        target_dir, output_dir = create_project_structure(project_name)
        
        # Copy and customize template files
        copy_and_customize_templates(target_dir, output_dir, project_name, target_url)
        
        print(f"\nProject successfully setup in {target_dir.resolve()}")
        proceed = input("Would you like to run the LIA wizard now? (y/n): ")
        if proceed == "y":
            run_lia_wizard(target_dir, target_url)
        else:
            print(f"To complete the setup, run the LIA wizard:")
            print(f"  cd {target_dir}")
            print(f"  python -m ethoscraper.setup --lia-wizard")
        
    except FileExistsError:
        return  # Already handled in create_project_structure
    except Exception as e:
        print(f"Error during setup: {e}")
        print("Please check your inputs and try again.")
        return


if __name__ == "__main__":
    main()
