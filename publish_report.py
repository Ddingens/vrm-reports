"""
Publish a new HTML report to vrm-reports.

Usage:
    py -3.13 publish_report.py <path_to_html_file>

The script will:
  1. Copy the file into the repo with a clean filename
  2. Update index.html to list it as "Latest" and archive previous latest
  3. Commit and push to GitHub (auto-deploys via Pages)
"""

import sys, os, re, shutil, subprocess
from datetime import date
from pathlib import Path

REPO_DIR = Path(__file__).parent.resolve()
INDEX_FILE = REPO_DIR / "index.html"

def slugify(name: str) -> str:
    """Convert filename to a clean slug: lowercase, underscores, no special chars."""
    name = Path(name).stem  # strip extension
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s-]+", "_", name.strip().lower())
    return name

def title_from_filename(name: str) -> str:
    """Derive a readable title from the filename."""
    stem = Path(name).stem
    # Remove trailing numbers like _11, _v2, etc.
    stem = re.sub(r"[_\s]*v?\d+$", "", stem, flags=re.IGNORECASE)
    return stem.replace("_", " ").replace("-", " ").title()

def extract_html_title(filepath: Path) -> str | None:
    """Try to pull <title> from the HTML file."""
    try:
        text = filepath.read_text(encoding="utf-8", errors="ignore")[:4000]
        m = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        if m:
            title = m.group(1).strip()
            # Skip generic titles
            if title and title.lower() not in ("document", "untitled", ""):
                return title
    except Exception:
        pass
    return None

def read_index() -> str:
    return INDEX_FILE.read_text(encoding="utf-8")

def parse_reports(html: str) -> list[dict]:
    """Extract the reports array from index.html."""
    m = re.search(r"const reports = \[(.*?)\];", html, re.DOTALL)
    if not m:
        return []
    block = m.group(1)
    reports = []
    for entry in re.finditer(
        r"\{(.*?)\}", block, re.DOTALL
    ):
        inner = entry.group(1)
        r = {}
        for key in ("title", "file", "date", "description"):
            km = re.search(rf'{key}:\s*"(.*?)"', inner)
            if km:
                r[key] = km.group(1)
        r["latest"] = "latest: true" in inner
        reports.append(r)
    return reports

def build_reports_js(reports: list[dict]) -> str:
    lines = []
    for r in reports:
        latest_str = "true" if r["latest"] else "false"
        lines.append(
            f'  {{\n'
            f'    title: "{r["title"]}",\n'
            f'    file: "{r["file"]}",\n'
            f'    date: "{r["date"]}",\n'
            f'    description: "{r["description"]}",\n'
            f'    latest: {latest_str}\n'
            f'  }}'
        )
    return "const reports = [\n" + ",\n".join(lines) + "\n];"

def update_index(reports: list[dict]) -> None:
    html = read_index()
    old = re.search(r"const reports = \[.*?\];", html, re.DOTALL).group(0)
    new = build_reports_js(reports)
    html = html.replace(old, new)
    INDEX_FILE.write_text(html, encoding="utf-8")

def git(*args):
    result = subprocess.run(
        ["git"] + list(args),
        cwd=REPO_DIR, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  git error: {result.stderr.strip()}")
        sys.exit(1)
    return result.stdout.strip()

def main():
    if len(sys.argv) < 2:
        print("Usage: py -3.13 publish_report.py <path_to_html_file>")
        sys.exit(1)

    source = Path(sys.argv[1]).resolve()
    if not source.exists():
        print(f"File not found: {source}")
        sys.exit(1)

    today = date.today().isoformat()

    # Determine report name
    slug = slugify(source.name)
    dest_name = f"{slug}.html"
    dest_path = REPO_DIR / dest_name

    # Check for overwrite
    if dest_path.exists():
        # Archive current version with date prefix
        archived_name = f"{today}_{slug}.html"
        print(f"  Archiving existing {dest_name} → {archived_name}")
        shutil.move(str(dest_path), str(REPO_DIR / archived_name))

    # Derive title
    html_title = extract_html_title(source)
    file_title = title_from_filename(source.name)

    print(f"\n  New report: {dest_name}")
    print(f"  Title from HTML: {html_title or '(none found)'}")
    print(f"  Title from file: {file_title}")

    title = html_title or file_title
    use_title = input(f"\n  Report title [{title}]: ").strip()
    if use_title:
        title = use_title

    description = input("  Description (optional): ").strip()
    if not description:
        description = title

    # Copy file in
    shutil.copy2(str(source), str(dest_path))
    print(f"\n  Copied → {dest_name}")

    # Update registry
    reports = parse_reports(read_index())

    # Archive previous latest
    for r in reports:
        if r["latest"]:
            r["latest"] = False

    # Add new entry at top
    reports.insert(0, {
        "title": title,
        "file": dest_name,
        "date": today,
        "description": description,
        "latest": True,
    })

    update_index(reports)
    print("  Updated index.html")

    # Git commit + push
    git("add", "-A")
    git("commit", "-m", f"Add report: {title} ({today})")
    git("push")
    print(f"\n  Published! View at: https://ddingens.github.io/vrm-reports/")
    print(f"  Direct link: https://ddingens.github.io/vrm-reports/{dest_name}")

if __name__ == "__main__":
    main()
