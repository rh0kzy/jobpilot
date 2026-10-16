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
    """Keep a raw feed item when its title or tags contain a target role/skill phrase."""
    if not roles:
        return True

    title_norm = _norm(title)
    title_tokens = set(title_norm.split())
    tag_text = _norm(" ".join(tags or []))

    for role in roles:
        for alias in _role_aliases(role):
            if not alias:
                continue
            if alias in title_norm:
                return True
            alias_tokens = set(alias.split())
            if alias_tokens and alias_tokens.issubset(title_tokens):
                return True
            if alias in tag_text and title_tokens & {"developer", "engineer", "programmer", "architect", "scientist", "analyst"}:
                return True
    return False
