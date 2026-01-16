#!/usr/bin/env python3
"""
Combined Permission Discovery Tool

Runs both backend and frontend permission discovery and generates
a comprehensive report. Can also run in CI mode to check for issues.

Usage:
    python tools/perm_discovery.py [--ci] [--output DIR]

Options:
    --ci            CI mode: exit with non-zero if issues found
    --output DIR    Output directory for reports (default: ./reports)
    --check-only    Only check for issues, don't generate full report
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_backend_discovery() -> dict:
    """Run backend permission discovery."""
    try:
        result = subprocess.run(
            [sys.executable, "tools/perm_discovery_backend.py", "--format", "json"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {"error": result.stderr}
    except Exception as e:
        return {"error": str(e)}


def run_frontend_discovery() -> dict:
    """Run frontend permission discovery."""
    try:
        result = subprocess.run(
            [sys.executable, "tools/perm_discovery_frontend.py", "--format", "json"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        else:
            return {"error": result.stderr}
    except Exception as e:
        return {"error": str(e)}


def check_issues(backend_data: dict, frontend_data: dict) -> dict:
    """Check for permission-related issues."""
    issues = {
        "unprotected_routes": [],
        "undefined_frontend_permissions": [],
        "unused_permissions": [],
        "missing_manifest_permissions": [],
    }

    # Check unprotected routes
    if "unprotected_routes" in backend_data:
        issues["unprotected_routes"] = backend_data["unprotected_routes"]

    # Check undefined frontend permissions
    if "undefined_permissions" in frontend_data:
        issues["undefined_frontend_permissions"] = frontend_data["undefined_permissions"]

    # Check for permissions in manifest but not used anywhere
    manifest_path = Path(__file__).parent.parent / "app" / "authz" / "permissions.manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = json.load(f)

        defined_perms = set(p["key"] for p in manifest.get("permissions", []))
        used_backend = set(backend_data.get("grouped_by_permission", {}).keys())
        used_frontend = set(frontend_data.get("aggregated", {}).get("permissions", {}).keys())

        # Filter out special permissions
        used_backend = {p for p in used_backend if not p.startswith("__")}

        all_used = used_backend | used_frontend
        issues["unused_permissions"] = sorted(list(defined_perms - all_used))

    return issues


def generate_report(backend_data: dict, frontend_data: dict, issues: dict) -> str:
    """Generate comprehensive markdown report."""
    lines = []

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines.append("# Permission Discovery Report")
    lines.append("")
    lines.append(f"Generated: {timestamp}")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")

    backend_summary = backend_data.get("summary", {})
    frontend_summary = frontend_data.get("summary", {})

    lines.append("### Backend")
    lines.append(f"- Total API Routes: {backend_summary.get('total_routes', 'N/A')}")
    lines.append(f"- Protected Routes: {backend_summary.get('protected_routes', 'N/A')}")
    lines.append(f"- Unprotected Routes: {backend_summary.get('unprotected_routes', 'N/A')}")
    lines.append(f"- Unique Permissions: {backend_summary.get('unique_permissions', 'N/A')}")
    lines.append("")

    lines.append("### Frontend")
    lines.append(f"- Files Scanned: {frontend_summary.get('files_scanned', 'N/A')}")
    lines.append(f"- Unique Permissions Used: {frontend_summary.get('unique_permissions', 'N/A')}")
    lines.append(f"- Modules Referenced: {frontend_summary.get('unique_modules', 'N/A')}")
    lines.append("")

    # Issues Section
    lines.append("## Issues")
    lines.append("")

    total_issues = 0

    # Unprotected routes
    unprotected = issues.get("unprotected_routes", [])
    if unprotected:
        total_issues += len(unprotected)
        lines.append(f"### Unprotected Routes ({len(unprotected)})")
        lines.append("")
        lines.append("These routes do not have permission requirements:")
        lines.append("")
        lines.append("| Method | Path |")
        lines.append("|--------|------|")
        for route in unprotected[:20]:  # Limit to 20
            for method in route.get("methods", []):
                lines.append(f"| {method} | `{route.get('path', '')}` |")
        if len(unprotected) > 20:
            lines.append(f"| ... | +{len(unprotected) - 20} more |")
        lines.append("")

    # Undefined frontend permissions
    undefined = issues.get("undefined_frontend_permissions", [])
    if undefined:
        total_issues += len(undefined)
        lines.append(f"### Undefined Frontend Permissions ({len(undefined)})")
        lines.append("")
        lines.append("These permissions are used in frontend but not defined in manifest:")
        lines.append("")
        for perm in undefined:
            lines.append(f"- `{perm}`")
        lines.append("")

    # Unused permissions
    unused = issues.get("unused_permissions", [])
    if unused:
        lines.append(f"### Unused Permissions ({len(unused)})")
        lines.append("")
        lines.append("These permissions are defined in manifest but not used anywhere:")
        lines.append("")
        for perm in unused[:20]:
            lines.append(f"- `{perm}`")
        if len(unused) > 20:
            lines.append(f"- ... +{len(unused) - 20} more")
        lines.append("")

    if total_issues == 0:
        lines.append("No critical issues found.")
        lines.append("")

    # Detailed Backend Section
    lines.append("## Backend Permission Mapping")
    lines.append("")

    grouped = backend_data.get("grouped_by_permission", {})
    for perm, routes in sorted(grouped.items()):
        if perm.startswith("__"):
            continue
        lines.append(f"### `{perm}`")
        lines.append("")
        lines.append("| Method | Path |")
        lines.append("|--------|------|")
        for route in routes:
            for method in route.get("methods", []):
                lines.append(f"| {method} | `{route.get('path', '')}` |")
        lines.append("")

    # Detailed Frontend Section
    lines.append("## Frontend Permission Usage")
    lines.append("")

    permissions = frontend_data.get("aggregated", {}).get("permissions", {})
    for perm, usages in sorted(permissions.items()):
        lines.append(f"### `{perm}`")
        lines.append("")
        lines.append("Files:")
        for usage in usages:
            file_name = usage["file"].split("/")[-1]
            lines.append(f"- `{file_name}` (lines: {', '.join(map(str, usage.get('lines', [])[:5]))})")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Combined permission discovery tool"
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="CI mode: exit with non-zero if critical issues found"
    )
    parser.add_argument(
        "--output", "-o",
        default="./reports",
        help="Output directory for reports"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check for issues"
    )

    args = parser.parse_args()

    print("Running permission discovery...", file=sys.stderr)

    # Run discoveries
    print("  Scanning backend routes...", file=sys.stderr)
    backend_data = run_backend_discovery()

    print("  Scanning frontend code...", file=sys.stderr)
    frontend_data = run_frontend_discovery()

    # Check for issues
    print("  Checking for issues...", file=sys.stderr)
    issues = check_issues(backend_data, frontend_data)

    # Calculate issue counts
    critical_issues = len(issues.get("unprotected_routes", [])) + len(issues.get("undefined_frontend_permissions", []))
    warning_issues = len(issues.get("unused_permissions", []))

    print(f"\nResults:", file=sys.stderr)
    print(f"  Critical Issues: {critical_issues}", file=sys.stderr)
    print(f"  Warnings: {warning_issues}", file=sys.stderr)

    if not args.check_only:
        # Generate report
        report = generate_report(backend_data, frontend_data, issues)

        # Create output directory
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        report_path = output_dir / f"permission_report_{timestamp}.md"
        with open(report_path, "w") as f:
            f.write(report)
        print(f"  Report: {report_path}", file=sys.stderr)

        # Write JSON data
        json_path = output_dir / f"permission_data_{timestamp}.json"
        with open(json_path, "w") as f:
            json.dump({
                "backend": backend_data,
                "frontend": frontend_data,
                "issues": issues,
            }, f, indent=2, ensure_ascii=False)
        print(f"  JSON Data: {json_path}", file=sys.stderr)

    # CI mode exit code
    if args.ci and critical_issues > 0:
        print(f"\nCI Check Failed: {critical_issues} critical issues found", file=sys.stderr)
        sys.exit(1)

    print("\nDone.", file=sys.stderr)


if __name__ == "__main__":
    main()
