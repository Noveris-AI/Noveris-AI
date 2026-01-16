#!/usr/bin/env python3
"""
Backend Permission Discovery Tool

Scans FastAPI routes to discover permission requirements and generate
API resource mappings for the permissions manifest.

Usage:
    python tools/perm_discovery_backend.py [--output OUTPUT_FILE] [--update-manifest]

Options:
    --output FILE       Output file for discovered permissions (default: stdout)
    --update-manifest   Update permissions.manifest.json with discovered API resources
    --format FORMAT     Output format: json, table, markdown (default: json)
"""

import argparse
import inspect
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import Depends
from fastapi.routing import APIRoute


def extract_permission_from_dependency(dep: Any) -> str | None:
    """Extract permission key from RequirePermission dependency."""
    if hasattr(dep, "dependency"):
        dep = dep.dependency

    # Check if it's a RequirePermission instance
    class_name = getattr(type(dep), "__name__", "")
    if class_name == "RequirePermission":
        return getattr(dep, "permission_key", None)
    elif class_name == "RequireModule":
        return f"__module__:{getattr(dep, 'module_key', '')}"
    elif class_name == "RequireSuperAdmin":
        return "__super_admin__"
    elif class_name in ("RequireAnyPermission", "RequireAllPermissions"):
        keys = getattr(dep, "permission_keys", [])
        return ",".join(keys) if keys else None

    return None


def get_route_permissions(route: APIRoute) -> list[str]:
    """Extract permission requirements from a route."""
    permissions = []

    # Check route dependencies
    if hasattr(route, "dependencies"):
        for dep in route.dependencies or []:
            perm = extract_permission_from_dependency(dep)
            if perm:
                permissions.append(perm)

    # Also check endpoint dependencies (from Depends() in function signature)
    endpoint = route.endpoint
    if endpoint and hasattr(endpoint, "__wrapped__"):
        endpoint = endpoint.__wrapped__

    if endpoint:
        try:
            sig = inspect.signature(endpoint)
            for param in sig.parameters.values():
                if param.default is not inspect.Parameter.empty:
                    if isinstance(param.default, Depends):
                        perm = extract_permission_from_dependency(param.default)
                        if perm:
                            permissions.append(perm)
        except (ValueError, TypeError):
            pass

    return permissions


def discover_routes(app) -> list[dict]:
    """Discover all routes and their permission requirements."""
    routes = []

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue

        # Get route info
        path = route.path
        methods = list(route.methods - {"HEAD", "OPTIONS"}) if route.methods else []
        name = route.name or ""
        tags = list(route.tags) if route.tags else []

        # Get permissions
        permissions = get_route_permissions(route)

        # Get operation ID
        operation_id = route.operation_id or name

        routes.append({
            "path": path,
            "methods": methods,
            "name": name,
            "operation_id": operation_id,
            "tags": tags,
            "permissions": permissions,
            "has_permission": len(permissions) > 0,
        })

    return routes


def group_by_permission(routes: list[dict]) -> dict[str, list[dict]]:
    """Group routes by permission key."""
    grouped = defaultdict(list)

    for route in routes:
        for perm in route.get("permissions", []):
            grouped[perm].append({
                "path": route["path"],
                "methods": route["methods"],
                "operation_id": route["operation_id"],
            })

    return dict(grouped)


def generate_api_resources(grouped: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Generate API resources structure for manifest."""
    resources = {}

    for perm_key, routes in grouped.items():
        if perm_key.startswith("__"):
            continue

        resources[perm_key] = []
        for route in routes:
            for method in route["methods"]:
                resources[perm_key].append({
                    "method": method,
                    "path": route["path"],
                    "operation_id": route["operation_id"],
                })

    return resources


def find_unprotected_routes(routes: list[dict], exclude_patterns: list[str] = None) -> list[dict]:
    """Find routes without permission requirements."""
    exclude = exclude_patterns or [
        r"^/docs",
        r"^/redoc",
        r"^/openapi",
        r"^/api/v1/health",
        r"^/api/v1/auth/login",
        r"^/api/v1/auth/register",
        r"^/api/v1/auth/forgot-password",
        r"^/api/v1/auth/reset-password",
        r"^/api/v1/auth/verify-email",
        r"^/api/v1/sso",
    ]

    unprotected = []
    for route in routes:
        if route["has_permission"]:
            continue

        path = route["path"]
        if any(re.match(pattern, path) for pattern in exclude):
            continue

        unprotected.append(route)

    return unprotected


def update_manifest(manifest_path: Path, api_resources: dict[str, list[dict]]) -> dict:
    """Update manifest file with discovered API resources."""
    with open(manifest_path) as f:
        manifest = json.load(f)

    updated_count = 0

    for perm in manifest.get("permissions", []):
        key = perm.get("key")
        if key in api_resources:
            if "api" not in perm:
                perm["api"] = {}
            perm["api"]["resources"] = api_resources[key]
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

        # Routes summary
        routes = data.get("routes", [])
        protected = sum(1 for r in routes if r["has_permission"])
        lines.append(f"Total Routes: {len(routes)}")
        lines.append(f"Protected Routes: {protected}")
        lines.append(f"Unprotected Routes: {len(routes) - protected}")
        lines.append("")

        # Protected routes table
        lines.append("Protected Routes:")
        lines.append("-" * 100)
        lines.append(f"{'METHOD':<10} {'PATH':<50} {'PERMISSION':<40}")
        lines.append("-" * 100)

        for route in sorted(routes, key=lambda x: x["path"]):
            if route["has_permission"]:
                for method in route["methods"]:
                    perms = ", ".join(route["permissions"])
                    lines.append(f"{method:<10} {route['path']:<50} {perms:<40}")

        lines.append("")

        # Unprotected routes
        unprotected = data.get("unprotected_routes", [])
        if unprotected:
            lines.append("Unprotected Routes (WARNING):")
            lines.append("-" * 100)
            for route in sorted(unprotected, key=lambda x: x["path"]):
                for method in route["methods"]:
                    lines.append(f"{method:<10} {route['path']:<50}")

        return "\n".join(lines)

    elif format_type == "markdown":
        lines = []

        routes = data.get("routes", [])
        protected = sum(1 for r in routes if r["has_permission"])

        lines.append("# API Permission Discovery Report")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total Routes:** {len(routes)}")
        lines.append(f"- **Protected Routes:** {protected}")
        lines.append(f"- **Unprotected Routes:** {len(routes) - protected}")
        lines.append("")

        # Group by permission
        grouped = data.get("grouped_by_permission", {})
        lines.append("## Permissions and Routes")
        lines.append("")

        for perm, perm_routes in sorted(grouped.items()):
            lines.append(f"### `{perm}`")
            lines.append("")
            lines.append("| Method | Path |")
            lines.append("|--------|------|")
            for route in perm_routes:
                for method in route["methods"]:
                    lines.append(f"| {method} | `{route['path']}` |")
            lines.append("")

        # Unprotected
        unprotected = data.get("unprotected_routes", [])
        if unprotected:
            lines.append("## Unprotected Routes (WARNING)")
            lines.append("")
            lines.append("| Method | Path |")
            lines.append("|--------|------|")
            for route in sorted(unprotected, key=lambda x: x["path"]):
                for method in route["methods"]:
                    lines.append(f"| {method} | `{route['path']}` |")

        return "\n".join(lines)

    return str(data)


def main():
    parser = argparse.ArgumentParser(
        description="Discover API permissions from FastAPI routes"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--update-manifest",
        action="store_true",
        help="Update permissions.manifest.json with API resources"
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "table", "markdown"],
        default="json",
        help="Output format (default: json)"
    )

    args = parser.parse_args()

    # Import app
    try:
        from app.main import app
    except ImportError as e:
        print(f"Error: Could not import FastAPI app: {e}", file=sys.stderr)
        print("Make sure you're running from the Backend directory.", file=sys.stderr)
        sys.exit(1)

    # Discover routes
    routes = discover_routes(app)
    grouped = group_by_permission(routes)
    api_resources = generate_api_resources(grouped)
    unprotected = find_unprotected_routes(routes)

    # Prepare output data
    data = {
        "routes": routes,
        "grouped_by_permission": grouped,
        "api_resources": api_resources,
        "unprotected_routes": unprotected,
        "summary": {
            "total_routes": len(routes),
            "protected_routes": sum(1 for r in routes if r["has_permission"]),
            "unprotected_routes": len(unprotected),
            "unique_permissions": len(grouped),
        },
    }

    # Update manifest if requested
    if args.update_manifest:
        manifest_path = Path(__file__).parent.parent / "app" / "authz" / "permissions.manifest.json"
        if manifest_path.exists():
            update_result = update_manifest(manifest_path, api_resources)
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
