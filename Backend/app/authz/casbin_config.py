"""
Casbin RBAC configuration and utilities.

This module provides Casbin integration for RBAC with domains/tenants.
"""

# Casbin model definition for RBAC with domains/tenants
# Supports role hierarchy, explicit deny, and priority-based evaluation

CASBIN_MODEL = """
[request_definition]
r = sub, dom, obj, act

[policy_definition]
p = sub, dom, obj, act, eft

[role_definition]
g = _, _, _

[policy_effect]
e = some(where (p.eft == allow)) && !some(where (p.eft == deny))

[matchers]
m = g(r.sub, p.sub, r.dom) && r.dom == p.dom && keyMatch2(r.obj, p.obj) && regexMatch(r.act, p.act)
"""

# Alternative model with priority support
CASBIN_MODEL_WITH_PRIORITY = """
[request_definition]
r = sub, dom, obj, act

[policy_definition]
p = sub, dom, obj, act, eft, priority

[role_definition]
g = _, _, _

[policy_effect]
e = priority(p.eft) || deny

[matchers]
m = g(r.sub, p.sub, r.dom) && r.dom == p.dom && keyMatch2(r.obj, p.obj) && regexMatch(r.act, p.act)
"""

# Simple model for basic RBAC (no deny support, faster)
CASBIN_MODEL_SIMPLE = """
[request_definition]
r = sub, dom, obj, act

[policy_definition]
p = sub, dom, obj, act

[role_definition]
g = _, _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub, r.dom) && r.dom == p.dom && keyMatch2(r.obj, p.obj) && regexMatch(r.act, p.act)
"""


def get_model_text(with_deny: bool = True, with_priority: bool = False) -> str:
    """
    Get the appropriate Casbin model based on requirements.

    Args:
        with_deny: Enable explicit deny support
        with_priority: Enable priority-based evaluation

    Returns:
        Casbin model definition string
    """
    if with_priority:
        return CASBIN_MODEL_WITH_PRIORITY
    elif with_deny:
        return CASBIN_MODEL
    else:
        return CASBIN_MODEL_SIMPLE
