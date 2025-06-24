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
    
    target_url = input("What is the url of the website you want to scrape?: ").strip()
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
