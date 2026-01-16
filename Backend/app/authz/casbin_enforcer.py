"""
Casbin enforcer management.

Provides async-compatible Casbin enforcer with caching support.
"""

import asyncio
import io
from functools import lru_cache
from typing import Optional, Set, Tuple

import casbin
from casbin import Enforcer
from casbin.model import Model

from app.authz.casbin_config import get_model_text


class CasbinEnforcerManager:
    """
    Manages Casbin enforcer instances with caching.

    This class provides a singleton-like pattern for Casbin enforcer
    with support for policy reloading and caching.
    """

    _instance: Optional["CasbinEnforcerManager"] = None
    _enforcer: Optional[Enforcer] = None
    _lock: asyncio.Lock

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    def _create_model(self, with_deny: bool = True) -> Model:
        """Create Casbin model from text definition."""
        model = Model()
        model_text = get_model_text(with_deny=with_deny)

        # Load model from text
        model.load_model_from_text(model_text)
        return model

    def get_enforcer(self, with_deny: bool = True) -> Enforcer:
        """
        Get or create the Casbin enforcer.

        Args:
            with_deny: Enable explicit deny support

        Returns:
            Casbin Enforcer instance
        """
        if self._enforcer is None:
            model = self._create_model(with_deny=with_deny)
            self._enforcer = Enforcer(model)

        return self._enforcer

    async def load_policies_from_db(
        self,
        policies: list[Tuple[str, str, str, str, str]],
        role_mappings: list[Tuple[str, str, str]],
    ) -> None:
        """
        Load policies from database into Casbin.

        Args:
            policies: List of (subject, domain, object, action, effect) tuples
            role_mappings: List of (user, role, domain) tuples for role inheritance
        """
        async with self._lock:
            enforcer = self.get_enforcer()

            # Clear existing policies
            enforcer.clear_policy()

            # Add policies
            for policy in policies:
                sub, dom, obj, act, eft = policy
                enforcer.add_named_policy("p", sub, dom, obj, act, eft)

            # Add role mappings (user -> role in domain)
            for mapping in role_mappings:
                user, role, domain = mapping
                enforcer.add_named_grouping_policy("g", user, role, domain)

    def enforce(
        self,
        subject: str,
        domain: str,
        obj: str,
        action: str,
    ) -> bool:
        """
        Check if subject has permission for action on object in domain.

        Args:
            subject: User ID or role name
            domain: Tenant ID
            obj: Permission key or resource path
            action: Action (view, create, update, delete, etc.)

        Returns:
            True if allowed, False otherwise
        """
        enforcer = self.get_enforcer()
        return enforcer.enforce(subject, domain, obj, action)

    def get_roles_for_user(self, user: str, domain: str) -> list[str]:
        """Get all roles for a user in a domain."""
        enforcer = self.get_enforcer()
        return enforcer.get_roles_for_user_in_domain(user, domain)

    def get_permissions_for_role(self, role: str, domain: str) -> list[list[str]]:
        """Get all permissions for a role in a domain."""
        enforcer = self.get_enforcer()
        return enforcer.get_permissions_for_user_in_domain(role, domain)


# Global enforcer manager instance
_enforcer_manager: Optional[CasbinEnforcerManager] = None


def get_enforcer_manager() -> CasbinEnforcerManager:
    """Get the global enforcer manager instance."""
    global _enforcer_manager
    if _enforcer_manager is None:
        _enforcer_manager = CasbinEnforcerManager()
    return _enforcer_manager
