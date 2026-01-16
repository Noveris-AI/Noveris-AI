"""
SSRF Protection Guard.

This module provides Server-Side Request Forgery (SSRF) protection
for the gateway's upstream HTTP calls.

Protection includes:
- IP address validation against blocked CIDRs
- DNS rebinding protection
- Redirect validation
- Protocol restriction

Reference: OWASP SSRF Prevention Cheat Sheet
"""

import ipaddress
import socket
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse

import httpx


class SSRFError(Exception):
    """Exception raised when SSRF protection is triggered."""

    def __init__(self, message: str, url: str = "", resolved_ip: str = ""):
        super().__init__(message)
        self.message = message
        self.url = url
        self.resolved_ip = resolved_ip


class SSRFGuard:
    """
    SSRF protection for HTTP requests.

    Validates URLs and prevents requests to:
    - Private IP ranges (10.x.x.x, 172.16.x.x, 192.168.x.x)
    - Loopback addresses (127.x.x.x, ::1)
    - Link-local addresses (169.254.x.x, fe80::)
    - Cloud metadata services (169.254.169.254)
    - IPv6 variants of the above

    Also validates:
    - Protocol (only http/https allowed)
    - Redirect targets
    - DNS resolution results
    """

    # Default blocked CIDR ranges
    DEFAULT_BLOCKED_CIDRS = [
        # IPv4 private/special
        "0.0.0.0/8",        # Current network
        "10.0.0.0/8",       # Private Class A
        "100.64.0.0/10",    # Carrier-grade NAT
        "127.0.0.0/8",      # Loopback
        "169.254.0.0/16",   # Link-local (includes AWS metadata)
        "172.16.0.0/12",    # Private Class B
        "192.0.0.0/24",     # IETF Protocol Assignments
        "192.0.2.0/24",     # TEST-NET-1
        "192.88.99.0/24",   # 6to4 Relay Anycast
        "192.168.0.0/16",   # Private Class C
        "198.18.0.0/15",    # Network Interconnect Device Benchmark
        "198.51.100.0/24",  # TEST-NET-2
        "203.0.113.0/24",   # TEST-NET-3
        "224.0.0.0/4",      # Multicast
        "240.0.0.0/4",      # Reserved
        "255.255.255.255/32",  # Broadcast

        # IPv6 special
        "::1/128",          # Loopback
        "::/128",           # Unspecified
        "::ffff:0:0/96",    # IPv4-mapped IPv6
        "64:ff9b::/96",     # IPv4/IPv6 translation
        "100::/64",         # Discard prefix
        "2001::/32",        # Teredo
        "2001:10::/28",     # ORCHID
        "2001:20::/28",     # ORCHIDv2
        "2001:db8::/32",    # Documentation
        "2002::/16",        # 6to4
        "fc00::/7",         # Unique local address
        "fe80::/10",        # Link-local
        "ff00::/8",         # Multicast
    ]

    # Additional blocked hosts (cloud metadata endpoints)
    BLOCKED_HOSTS = {
        "metadata.google.internal",
        "metadata.goog",
        "169.254.169.254",  # AWS/GCP/Azure metadata
        "metadata",
        "instance-data",
    }

    def __init__(
        self,
        blocked_cidrs: Optional[List[str]] = None,
        additional_blocked_hosts: Optional[Set[str]] = None
    ):
        """
        Initialize SSRF guard.

        Args:
            blocked_cidrs: Additional CIDRs to block (merged with defaults)
            additional_blocked_hosts: Additional hostnames to block
        """
        # Parse blocked CIDRs
        all_cidrs = self.DEFAULT_BLOCKED_CIDRS.copy()
        if blocked_cidrs:
            all_cidrs.extend(blocked_cidrs)

        self.blocked_networks = []
        for cidr in all_cidrs:
            try:
                self.blocked_networks.append(ipaddress.ip_network(cidr, strict=False))
            except ValueError:
                pass  # Skip invalid CIDRs

        # Blocked hosts
        self.blocked_hosts = self.BLOCKED_HOSTS.copy()
        if additional_blocked_hosts:
            self.blocked_hosts.update(additional_blocked_hosts)

    def validate_url(
        self,
        url: str,
        allow_hosts: Optional[List[str]] = None,
        allow_cidrs: Optional[List[str]] = None
    ) -> Tuple[str, List[str]]:
        """
        Validate a URL for SSRF protection.

        Args:
            url: URL to validate
            allow_hosts: Optional allowlist of hostnames
            allow_cidrs: Optional allowlist of CIDRs

        Returns:
            Tuple of (validated URL, resolved IPs)

        Raises:
            SSRFError: If URL fails validation
        """
        parsed = urlparse(url)

        # 1. Validate scheme
        if parsed.scheme not in ("http", "https"):
            raise SSRFError(
                f"Invalid scheme: {parsed.scheme}. Only http/https allowed.",
                url=url
            )

        # 2. Validate hostname
        hostname = parsed.hostname
        if not hostname:
            raise SSRFError("Missing hostname", url=url)

        # Check blocked hosts
        hostname_lower = hostname.lower()
        if hostname_lower in self.blocked_hosts:
            raise SSRFError(
                f"Blocked host: {hostname}",
                url=url
            )

        # 3. Resolve DNS and validate IPs
        try:
            resolved_ips = self._resolve_hostname(hostname)
        except socket.gaierror as e:
            raise SSRFError(
                f"DNS resolution failed for {hostname}: {e}",
                url=url
            )

        if not resolved_ips:
            raise SSRFError(
                f"No IP addresses found for {hostname}",
                url=url
            )

        # 4. Validate each resolved IP
        for ip_str in resolved_ips:
            self._validate_ip(ip_str, url, allow_cidrs)

        # 5. Check against allowlist if provided
        if allow_hosts is not None:
            if hostname_lower not in [h.lower() for h in allow_hosts]:
                raise SSRFError(
                    f"Host {hostname} not in allowlist",
                    url=url
                )

        return url, resolved_ips

    def _resolve_hostname(self, hostname: str) -> List[str]:
        """Resolve hostname to IP addresses."""
        # Handle IP address literals
        try:
            ipaddress.ip_address(hostname)
            return [hostname]
        except ValueError:
            pass

        # DNS resolution
        results = []
        try:
            # Get both IPv4 and IPv6 addresses
            infos = socket.getaddrinfo(
                hostname, None,
                socket.AF_UNSPEC,
                socket.SOCK_STREAM
            )
            for info in infos:
                ip = info[4][0]
                if ip not in results:
                    results.append(ip)
        except socket.gaierror:
            raise

        return results

    def _validate_ip(
        self,
        ip_str: str,
        url: str,
        allow_cidrs: Optional[List[str]] = None
    ) -> None:
        """Validate an IP address against blocked ranges."""
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFError(
                f"Invalid IP address: {ip_str}",
                url=url,
                resolved_ip=ip_str
            )

        # Check against blocked networks
        for network in self.blocked_networks:
            if ip in network:
                raise SSRFError(
                    f"IP {ip_str} is in blocked range {network}",
                    url=url,
                    resolved_ip=ip_str
                )

        # If allowlist provided, check against it
        if allow_cidrs is not None:
            allowed = False
            for cidr in allow_cidrs:
                try:
                    network = ipaddress.ip_network(cidr, strict=False)
                    if ip in network:
                        allowed = True
                        break
                except ValueError:
                    continue

            if not allowed:
                raise SSRFError(
                    f"IP {ip_str} not in allowed CIDRs",
                    url=url,
                    resolved_ip=ip_str
                )

    def validate_redirect(
        self,
        original_url: str,
        redirect_url: str,
        allow_hosts: Optional[List[str]] = None,
        allow_cidrs: Optional[List[str]] = None
    ) -> Tuple[str, List[str]]:
        """
        Validate a redirect URL.

        Prevents redirect-based SSRF attacks where the initial URL
        is valid but redirects to a blocked address.

        Args:
            original_url: The original request URL
            redirect_url: The redirect target URL
            allow_hosts: Optional allowlist of hostnames
            allow_cidrs: Optional allowlist of CIDRs

        Returns:
            Tuple of (validated URL, resolved IPs)

        Raises:
            SSRFError: If redirect fails validation
        """
        # Resolve relative redirects
        if not redirect_url.startswith(("http://", "https://")):
            parsed_original = urlparse(original_url)
            if redirect_url.startswith("/"):
                redirect_url = f"{parsed_original.scheme}://{parsed_original.netloc}{redirect_url}"
            else:
                raise SSRFError(
                    f"Invalid redirect URL: {redirect_url}",
                    url=redirect_url
                )

        # Validate the redirect URL
        return self.validate_url(redirect_url, allow_hosts, allow_cidrs)


class SSRFProtectedTransport(httpx.AsyncHTTPTransport):
    """
    Custom httpx transport with SSRF protection.

    Validates all request URLs and redirect targets before connecting.
    """

    def __init__(
        self,
        ssrf_guard: SSRFGuard,
        allow_hosts: Optional[List[str]] = None,
        allow_cidrs: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.ssrf_guard = ssrf_guard
        self.allow_hosts = allow_hosts
        self.allow_cidrs = allow_cidrs

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle request with SSRF validation."""
        # Validate URL before making request
        self.ssrf_guard.validate_url(
            str(request.url),
            self.allow_hosts,
            self.allow_cidrs
        )

        return await super().handle_async_request(request)


# Singleton guard instance
_ssrf_guard: Optional[SSRFGuard] = None


def get_ssrf_guard(
    blocked_cidrs: Optional[List[str]] = None,
    additional_blocked_hosts: Optional[Set[str]] = None
) -> SSRFGuard:
    """Get or create the singleton SSRF guard."""
    global _ssrf_guard
    if _ssrf_guard is None:
        _ssrf_guard = SSRFGuard(blocked_cidrs, additional_blocked_hosts)
    return _ssrf_guard


def create_ssrf_protected_client(
    ssrf_guard: Optional[SSRFGuard] = None,
    allow_hosts: Optional[List[str]] = None,
    allow_cidrs: Optional[List[str]] = None,
    **client_kwargs
) -> httpx.AsyncClient:
    """
    Create an httpx AsyncClient with SSRF protection.

    Args:
        ssrf_guard: SSRFGuard instance (uses default if not provided)
        allow_hosts: Optional allowlist of hostnames
        allow_cidrs: Optional allowlist of CIDRs
        **client_kwargs: Additional arguments for AsyncClient

    Returns:
        httpx.AsyncClient with SSRF protection
    """
    guard = ssrf_guard or get_ssrf_guard()

    transport = SSRFProtectedTransport(
        ssrf_guard=guard,
        allow_hosts=allow_hosts,
        allow_cidrs=allow_cidrs
    )

    return httpx.AsyncClient(
        transport=transport,
        follow_redirects=False,  # Handle redirects manually for validation
        **client_kwargs
    )
