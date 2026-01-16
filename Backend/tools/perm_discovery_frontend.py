#!/usr/bin/env python3
"""
Frontend Permission Discovery Tool

Scans frontend React/TypeScript code to discover permission usages
and generate UI route mappings for the permissions manifest.

Usage:
    python tools/perm_discovery_frontend.py [--output OUTPUT_FILE] [--update-manifest]

Options:
    --output FILE       Output file for discovered permissions (default: stdout)
    --update-manifest   Update permissions.manifest.json with discovered UI resources
    --format FORMAT     Output format: json, table, markdown (default: json)
    --src-dir DIR       Frontend source directory (default: ../Frontend/src)
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# Patterns to match permission usages
PERMISSION_PATTERNS = [
    # usePermission hook
    r'usePermission\s*\(\s*[\'"]([^"\']+)[\'"]\s*\)',
    # useAnyPermission hook
    r'useAnyPermission\s*\(\s*\[([^\]]+)\]\s*\)',
    # useAllPermissions hook
    r'useAllPermissions\s*\(\s*\[([^\]]+)\]\s*\)',
    # RequirePermission component
    r'<RequirePermission\s+permission=[\'"]([^"\']+)[\'"]',
    r'RequirePermission\s+permission=\{[\'"]([^"\']+)[\'"]\}',
    # RequireAnyPermission component
    r'<RequireAnyPermission\s+permissions=\{?\[([^\]]+)\]',
    # PermissionGate component
    r'<PermissionGate\s+permission=[\'"]([^"\']+)[\'"]',
    # hasPermission function call
    r'hasPermission\s*\(\s*[\'"]([^"\']+)[\'"]\s*\)',
    # checkPermission function call
    r'checkPermission\s*\(\s*[\'"]([^"\']+)[\'"]\s*\)',
]

# Module patterns
MODULE_PATTERNS = [
    # useModuleEnabled hook
    r'useModuleEnabled\s*\(\s*[\'"]([^"\']+)[\'"]\s*\)',
    # RequireModule component
    r'<RequireModule\s+module=[\'"]([^"\']+)[\'"]',
    r'RequireModule\s+module=\{[\'"]([^"\']+)[\'"]\}',
    # isModuleEnabled function call
    r'isModuleEnabled\s*\(\s*[\'"]([^"\']+)[\'"]\s*\)',
]

# Route patterns (for determining UI routes)
ROUTE_PATTERNS = [
    r'<Route\s+path=[\'"]([^"\']+)[\'"]',
    r'path:\s*[\'"]([^"\']+)[\'"]',
    r'navigate\s*\(\s*[\'"]([^"\']+)[\'"]',
    r'to=[\'"]([^"\']+)[\'"]',
]


def extract_permissions_from_array(array_str: str) -> list[str]:
    """Extract individual permissions from an array string like '"perm1", "perm2"'."""
    permissions = []
    # Match strings in quotes
    matches = re.findall(r'[\'"]([^"\']+)[\'"]', array_str)
    permissions.extend(matches)
    return permissions


def scan_file(file_path: Path) -> dict:
    """Scan a single file for permission usages."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    result = {
        "file": str(file_path),
        "permissions": [],
        "modules": [],
        "routes": [],
        "line_numbers": defaultdict(list),
    }

    lines = content.split("\n")

    # Find permissions
    for pattern in PERMISSION_PATTERNS:
        for match in re.finditer(pattern, content):
            perm_str = match.group(1)
            # Handle array syntax
            if "," in perm_str and not perm_str.startswith("["):
                perms = extract_permissions_from_array(perm_str)
            else:
                perms = [perm_str.strip().strip("'\"")]

            for perm in perms:
                if perm and perm not in result["permissions"]:
                    result["permissions"].append(perm)

                    # Find line number
                    start = match.start()
                    line_num = content[:start].count("\n") + 1
                    result["line_numbers"][perm].append(line_num)

    # Find modules
    for pattern in MODULE_PATTERNS:
        for match in re.finditer(pattern, content):
            module = match.group(1).strip().strip("'\"")
            if module and module not in result["modules"]:
                result["modules"].append(module)

    # Find routes in the file
    for pattern in ROUTE_PATTERNS:
        for match in re.finditer(pattern, content):
            route = match.group(1).strip()
            if route and route not in result["routes"] and route.startswith("/"):
                result["routes"].append(route)

    return result


def scan_directory(src_dir: Path, extensions: list[str] = None) -> list[dict]:
    """Scan all files in directory for permission usages."""
    extensions = extensions or [".tsx", ".ts", ".jsx", ".js"]
    results = []

    for root, dirs, files in os.walk(src_dir):
        # Skip node_modules and other common exclusions
        dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "dist", "build", "__pycache__"]]

        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_path = Path(root) / file
                result = scan_file(file_path)
                if result["permissions"] or result["modules"]:
                    results.append(result)

    return results


def aggregate_results(file_results: list[dict]) -> dict:
    """Aggregate results from all files."""
    permissions = defaultdict(list)
    modules = defaultdict(list)

    for result in file_results:
        file_path = result["file"]

        for perm in result["permissions"]:
            lines = result["line_numbers"].get(perm, [])
            permissions[perm].append({
                "file": file_path,
                "lines": lines,
                "routes": result["routes"],
            })

        for module in result["modules"]:
            modules[module].append({
                "file": file_path,
            })

    return {
        "permissions": dict(permissions),
        "modules": dict(modules),
    }


def infer_ui_routes(permission_usages: dict) -> dict[str, list[str]]:
    """Infer UI routes from file paths and content."""
    ui_routes = {}

    for perm, usages in permission_usages.items():
        routes = set()

        for usage in usages:
            file_path = usage["file"]

            # Extract routes found in the file
            routes.update(usage.get("routes", []))

            # Infer route from file path
            # e.g., pages/nodes/NodeListPage.tsx -> /dashboard/nodes
            path_match = re.search(r"pages/([^/]+)", file_path)
            if path_match:
                page_name = path_match.group(1).lower()
                routes.add(f"/dashboard/{page_name}")

            # Check for specific page patterns
            if "NodeListPage" in file_path or "nodes" in file_path.lower():
                routes.add("/dashboard/nodes")
            elif "JobListPage" in file_path or "jobs" in file_path.lower():
                routes.add("/dashboard/jobs")
            elif "DeploymentListPage" in file_path or "deployments" in file_path.lower():
                routes.add("/dashboard/deployment")
            elif "GatewayPage" in file_path or "gateway" in file_path.lower():
                routes.add("/dashboard/forwarding")
            elif "AuthzPage" in file_path or "authz" in file_path.lower() or "permissions" in file_path.lower():
                routes.add("/dashboard/permissions")

        ui_routes[perm] = sorted(list(routes))

    return ui_routes


def generate_ui_resources(permissions: dict, ui_routes: dict) -> dict[str, dict]:
    """Generate UI resources structure for manifest."""
    resources = {}

    for perm, usages in permissions.items():
        resources[perm] = {
            "routes": ui_routes.get(perm, []),
            "components": list(set(u["file"].split("/")[-1].replace(".tsx", "").replace(".ts", "") for u in usages)),
        }

    return resources


def find_undefined_permissions(used_permissions: set, manifest_path: Path) -> list[str]:
    """Find permissions used in code but not defined in manifest."""
    if not manifest_path.exists():
        return list(used_permissions)

    with open(manifest_path) as f:
        manifest = json.load(f)

    defined = set(p["key"] for p in manifest.get("permissions", []))
    return sorted(list(used_permissions - defined))


def update_manifest(manifest_path: Path, ui_resources: dict[str, dict]) -> dict:
    """Update manifest file with discovered UI resources."""
    if not manifest_path.exists():
        return {"error": "Manifest not found"}

    with open(manifest_path) as f:
        manifest = json.load(f)

    updated_count = 0

    for perm in manifest.get("permissions", []):
        key = perm.get("key")
        if key in ui_resources:
            if "ui" not in perm:
                perm["ui"] = {}

            # Merge routes
            existing_routes = set(perm["ui"].get("routes", []))
            new_routes = set(ui_resources[key].get("routes", []))
            perm["ui"]["routes"] = sorted(list(existing_routes | new_routes))

            updated_count += 1

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return {"updated_permissions": updated_count}


def format_output(data: dict, format_type: str) -> str:
    """Format output based on type."""
    if format_type == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)

    elif format_type == "table":
        lines = []

        permissions = data.get("aggregated", {}).get("permissions", {})
        modules = data.get("aggregated", {}).get("modules", {})

        lines.append(f"Unique Permissions Used: {len(permissions)}")
        lines.append(f"Modules Referenced: {len(modules)}")
        lines.append("")

        # Permissions table
        lines.append("Permissions Usage:")
        lines.append("-" * 100)
        lines.append(f"{'PERMISSION':<40} {'FILES':<50} {'USAGE COUNT':<10}")
        lines.append("-" * 100)

        for perm, usages in sorted(permissions.items()):
            files = ", ".join(u["file"].split("/")[-1] for u in usages[:3])
            if len(usages) > 3:
                files += f" (+{len(usages) - 3} more)"
            lines.append(f"{perm:<40} {files:<50} {len(usages):<10}")

        # Undefined permissions warning
        undefined = data.get("undefined_permissions", [])
        if undefined:
            lines.append("")
            lines.append("UNDEFINED PERMISSIONS (not in manifest):")
            lines.append("-" * 50)
            for perm in undefined:
                lines.append(f"  - {perm}")

        return "\n".join(lines)

    elif format_type == "markdown":
        lines = []

        permissions = data.get("aggregated", {}).get("permissions", {})
        modules = data.get("aggregated", {}).get("modules", {})

        lines.append("# Frontend Permission Discovery Report")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Unique Permissions:** {len(permissions)}")
        lines.append(f"- **Modules Referenced:** {len(modules)}")
        lines.append(f"- **Files Scanned:** {data.get('summary', {}).get('files_scanned', 0)}")
        lines.append("")

        # Permissions
        lines.append("## Permissions Usage")
        lines.append("")
        lines.append("| Permission | Files | Usage Count |")
        lines.append("|------------|-------|-------------|")

        for perm, usages in sorted(permissions.items()):
            files = ", ".join(f"`{u['file'].split('/')[-1]}`" for u in usages[:2])
            if len(usages) > 2:
                files += f" +{len(usages) - 2}"
            lines.append(f"| `{perm}` | {files} | {len(usages)} |")

        # Modules
        if modules:
            lines.append("")
            lines.append("## Module References")
            lines.append("")
            lines.append("| Module | Files |")
            lines.append("|--------|-------|")
            for module, usages in sorted(modules.items()):
                files = ", ".join(f"`{u['file'].split('/')[-1]}`" for u in usages[:3])
                lines.append(f"| `{module}` | {files} |")

        # Undefined
        undefined = data.get("undefined_permissions", [])
        if undefined:
            lines.append("")
            lines.append("## Undefined Permissions (WARNING)")
            lines.append("")
            lines.append("These permissions are used in code but not defined in the manifest:")
            lines.append("")
            for perm in undefined:
                lines.append(f"- `{perm}`")

        return "\n".join(lines)

    return str(data)


def main():
    parser = argparse.ArgumentParser(
        description="Discover permission usages in frontend code"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--update-manifest",
        action="store_true",
        help="Update permissions.manifest.json with UI resources"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "table", "markdown"],
        default="json",
        help="Output format (default: json)"
    )
    parser.add_argument(
        "--src-dir",
        default=None,
        help="Frontend source directory"
    )

    args = parser.parse_args()

    # Determine source directory
    if args.src_dir:
        src_dir = Path(args.src_dir)
    else:
        # Default: look for Frontend/src relative to this script
        src_dir = Path(__file__).parent.parent.parent / "Frontend" / "src"

    if not src_dir.exists():
        print(f"Error: Source directory not found: {src_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning: {src_dir}", file=sys.stderr)

    # Scan files
    file_results = scan_directory(src_dir)
    aggregated = aggregate_results(file_results)

    # Infer UI routes
    ui_routes = infer_ui_routes(aggregated["permissions"])
    ui_resources = generate_ui_resources(aggregated["permissions"], ui_routes)

    # Find undefined permissions
    manifest_path = Path(__file__).parent.parent / "app" / "authz" / "permissions.manifest.json"
    used_permissions = set(aggregated["permissions"].keys())
    undefined = find_undefined_permissions(used_permissions, manifest_path)

    # Prepare output data
    data = {
        "file_results": file_results,
        "aggregated": aggregated,
        "ui_routes": ui_routes,
        "ui_resources": ui_resources,
        "undefined_permissions": undefined,
        "summary": {
            "files_scanned": len(file_results),
            "unique_permissions": len(aggregated["permissions"]),
            "unique_modules": len(aggregated["modules"]),
            "undefined_count": len(undefined),
        },
    }

    # Update manifest if requested
    if args.update_manifest:
        if manifest_path.exists():
            update_result = update_manifest(manifest_path, ui_resources)
            data["manifest_update"] = update_result
            print(f"Updated manifest: {update_result}", file=sys.stderr)
        else:
            print(f"Warning: Manifest not found at {manifest_path}", file=sys.stderr)

    # Format and output
    output = format_output(data, args.format)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Output written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
