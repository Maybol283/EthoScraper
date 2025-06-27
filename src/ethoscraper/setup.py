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
        src = Path(__file__).parent / "templates" / name
        
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

    return needs_dpia, flagged
# ──────────────────────────────────────────────────────────────────────────────
# Legitimate Interest Assessment
# ──────────────────────────────────────────────────────────────────────────────

def purpose_test(target_url: str) -> list[str]:
    """Test if the purpose of the project is legitimate."""
    print(f"Testing if the purpose of the project is legitimate for {target_url} \n")
    
    questions = {
        "purpose_why": "1. Why are you scraping this website?",
        "benefit_org": "2. Benefit to our organisation?",
        "third_party": "3. Third-party benefits?",
        "public_benefit": "4. Wider public/societal benefits?",
        "no_process": "5. What if we couldn't process?",
        "positive_outcome": "6. Positive outcome for individuals?",
        "ethical_issues": "7. Are there any ethical issues with the processing?"
    }
    
    examples = {
        "purpose_why": [
            " To analyse trends in how UK residents discuss local",
            " air-quality measures on publicly available newspaper",
            " comment sections and community forums."
        ],
        "benefit_org": [
            " Peer-reviewed publications and REF impact case-study;",
            " Evidence base for grant applications on urban pollution",
            " mitigation."
        ],
        "third_party": [
            " Local authorities and campaign groups gain anonymised",
            " insights into public sentiment for policy design."
        ],
        "public_benefit": [
            " Better-targeted public-health messaging and",
            " environmental interventions."
        ],
        "no_process": [
            " We would rely on expensive, limited survey panels,",
            " missing authentic grassroots discourse."
        ],
        "positive_outcome": [
            " Voices expressed in small regional outlets are surfaced",
            " to policy-makers, potentially improving neighbourhood",
            " air quality."
        ],
        "ethical_issues": [
            " Risk of re-identifying individuals from small forums.",
            " Mitigated by aggregating data, removing usernames, and",
            " focusing on themes rather than individual opinions."
        ]
    }
    
    answers = []
    for key, question in questions.items():
        print("\nEXAMPLE:")
        for line in examples[key]:
            print(line)
        print()
        answer = input(f"{question} ")
        answers.append(answer)
    
    print(f"All answers have been recorded and can be edited in compliance.yaml")
    return answers

def necessity_test(target_url: str) -> list[str]:
    """Test if the data processing is necessary and proportionate."""
    print(f"Testing if the data processing is necessary for {target_url} \n")
    
    questions = {
        "helps_achieve": "1. Will the processing actually help you achieve your purpose?",
        "proportionate": "2. Is the processing proportionate to that purpose?",
        "achieve_without": "3. Can you achieve your purpose without processing the data, or by processing less data?",
        "less_intrusive": "4. Can you achieve your purpose by processing the data in another more obvious or less intrusive way?"
    }
    
    examples = {
        "helps_achieve": [
            " Yes, analysing public discourse requires processing the text",
            " content and associated metadata to identify themes and",
            " geographical patterns in air quality discussions."
        ],
        "proportionate": [
            " The processing is proportionate - we only collect publicly",
            " available comments and aggregate them for thematic analysis,",
            " not individual profiling or intrusive monitoring."
        ],
        "achieve_without": [
            " No, we cannot achieve meaningful trend analysis without",
            " processing the text data. However, we limit collection to",
            " relevant discussion threads only."
        ],
        "less_intrusive": [
            " Alternative approaches like surveys would be less",
            " representative and more intrusive. Public forum analysis",
            " is the least invasive method for this research question."
        ]
    }
    
    answers = []
    for key, question in questions.items():
        print("\nEXAMPLE:")
        for line in examples[key]:
            print(line)
        print()
        answer = input(f"{question} ")
        answers.append(answer)
    
    print(f"All answers have been recorded and can be edited in compliance.yaml")
    return answers

def balance_test(target_url: str) -> list[str]:
    """Test if the data processing is balanced."""
    print(f"Testing if the data processing is balanced for {target_url} \n")
    print("=== NATURE OF THE DATA ===\n")
    print("Please answer with Yes (Y) or No (N) \n")
    
    # Nature of Data questions
    nature_questions = {
        "special_category": "1. Are you processing special category data (racial/ethnic origin, political opinions, religious/philosophical beliefs, \n trade union membership, genetic data, biometric data, health data, sex life, sexual orientation)?",
        "criminal_data": "2. Are you processing criminal offence data (personal data relating to criminal convictions and offences or related security measures)?",
        "private_data": "3. Are you processing particularly 'private' data (financial, intimate personal details)?",
        "vulnerable_data": "4. Are you processing children's data or data from vulnerable individuals?",
        "personal_or_professional": "5. Is the data about people in their personal or professional capacity?"
    }
    
    # Examples for follow-up questions when answer is Yes
    followup_examples = {
        "criminal_data": [
            " We are processing conviction data from court records. Data includes conviction",
            " dates, offence types, and sentencing outcomes from publicly",
            " available court databases."
        ],
        "private_data": [
            " We are processing financial transaction data from bank",
            " statements. Data includes",
            " transaction amounts, merchant categories, and spending",
            " patterns from anonymized customer records."
        ],
        "vulnerable_data": [
            " We are processing educational records of children aged 13-16",
            " Data includes test scores,",
            " attendance records, and demographic information with parental",
            " consent and school ethics approval."
        ]
    }
    
    nature_examples = {
        "personal_or_professional": [
            " Mixed - some comments may be from individuals in personal",
            " capacity (residents discussing local air quality) and some",
            " in professional capacity (officials, experts)."
        ]
    }
    
    nature_answers = []
    for key, question in nature_questions.items():
        if key in nature_examples:
            print("\nEXAMPLE:")
            for line in nature_examples[key]:
                print(line)
            print()
        
        answer = input(f"{question} ")
        
        # Handle follow-up questions for Yes answers
        if answer in ["Y", "Yes", "y", "yes"] and key in followup_examples:
            print("\nEXAMPLE:")
            for line in followup_examples[key]:
                print(line)
            print()
            answer = input(f"Please specify which {key.replace('_', ' ')} you are processing: ")
        
        nature_answers.append(answer)
    
    # Reasonable Expectations section
    print("\n=== REASONABLE EXPECTATIONS ===\n")
    print("Please provide detailed answers \n")
    
    expectations_questions = {
        "existing_relationship": "1. Do you have an existing relationship with the individuals whose data you're processing? If so, what is the nature of that relationship?",
        "past_usage": "2. How have you used their data in the past?",
        "collected_directly": "3. Did you collect the data directly from the individuals?",
        "told_individuals": "4. What did you tell individuals at the time of collection?",
        "third_party_told": "5. If obtained from third party, what did they tell individuals about reuse by third parties?",
        "data_age_context": "6. How long ago was the data collected and are there any relevant changes since then?",
        "obvious_purpose": "7. Is your intended purpose and method obvious or widely understood?",
        "innovative_processing": "8. Are you doing anything new or innovative with the data?",
        "evidence_expectations": "9. Do you have evidence about expectations (market research, focus groups, consultation)?",
        "other_factors": "10. Are there other factors that would affect whether individuals expect this processing?"
    }
    
    expectations_examples = {
        "existing_relationship": [
            " No existing relationship - we are processing publicly",
            " available comments from newspaper websites and forums",
            " where individuals have no direct relationship with us."
        ],
        "past_usage": [
            " This is the first time we are processing data from these",
            " sources. We have not used their data previously."
        ],
        "collected_directly": [
            " No, the data is collected from third-party websites",
            " (newspaper comment sections and public forums) rather",
            " than directly from individuals."
        ],
        "told_individuals": [
            " Not applicable - we did not collect data directly from",
            " individuals. The data comes from public forums and",
            " newspaper comment sections."
        ],
        "third_party_told": [
            " The website terms of service typically state that comments",
            " may be used for research purposes or by third parties.",
            " Forum policies generally allow academic research use."
        ],
        "data_age_context": [
            " Data collection is current (within last 6 months).",
            " No significant technological or contextual changes",
            " since collection that would affect expectations."
        ],
        "obvious_purpose": [
            " Academic research on public environmental discourse is",
            " widely understood and accepted. The purpose of analyzing",
            " public sentiment on air quality is straightforward."
        ],
        "innovative_processing": [
            " The research methods are standard (thematic analysis",
            " of public comments). We are not using novel AI techniques",
            " or innovative processing methods."
        ],
        "evidence_expectations": [
            " We conducted focus groups with 20 local residents who",
            " confirmed they expect their public environmental comments",
            " to be used for legitimate academic research."
        ],
        "other_factors": [
            " The data subjects have chosen to post in public forums",
            " about environmental issues, suggesting they expect public",
            " visibility and potential research use of their comments."
        ]
    }
    
    expectations_answers = []
    for key, question in expectations_questions.items():
        print("\nEXAMPLE:")
        for line in expectations_examples[key]:
            print(line)
        print()
        answer = input(f"{question} ")
        expectations_answers.append(answer)
    
    return nature_answers + expectations_answers

# ──────────────────────────────────────────────────────────────────────────────
# Main orchestration
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:  # pragma: no cover
    """Main setup workflow orchestration."""
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
        
        print(f"Project successfully setup in {target_dir.resolve()}, Please enter the folder and run the LIA wizard to complete the project setup.")
        
    except FileExistsError:
        return  # Already handled in create_project_structure
    except Exception as e:
        print(f"Error during setup: {e}")
        print("Please check your inputs and try again.")
        return


if __name__ == "__main__":
    main()
