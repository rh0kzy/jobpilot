"""Cheap title/tag prefilter for connectors (no scoring)."""

import re


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _role_aliases(role: str) -> list[str]:
    normalized = _norm(role)
    aliases = {normalized}
    if "developer" in normalized:
        aliases.add(normalized.replace("developer", "engineer"))
    if "engineer" in normalized:
        aliases.add(normalized.replace("engineer", "developer"))
    if "fullstack" in normalized:
        aliases.add(normalized.replace("fullstack", "full stack"))
    if "full stack" in normalized:
        aliases.add(normalized.replace("full stack", "fullstack"))
    return sorted(aliases)


def matches_role(title: str, tags: list[str] | None = None, roles: list[str] | None = None) -> bool:
    """Keep a raw feed item only when its title matches a target role."""
    if not roles:
        return True

    title_norm = _norm(title)
    title_tokens = set(title_norm.split())

    for role in roles:
        for alias in _role_aliases(role):
            if not alias:
                continue
            if alias in title_norm or set(alias.split()).issubset(title_tokens):
                return True

    # Tags are only a secondary signal, and only when the job already looks
    # like an engineering/software role.
    title_role_tokens = {"developer", "engineer", "programmer", "architect", "engineering"}
    if title_tokens & title_role_tokens:
        tag_text = _norm(" ".join(tags or []))
        for role in roles:
            for alias in _role_aliases(role):
                if alias and alias in tag_text:
                    return True
    return False