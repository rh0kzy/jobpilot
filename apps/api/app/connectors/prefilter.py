"""Cheap title/tag prefilter for connectors (no scoring)."""

import re

_ADJACENT_TITLE_TERMS = {
    "backend",
    "frontend",
    "full stack",
    "fullstack",
    "mobile",
    "react native",
    "ios",
    "android",
    "ai",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "data engineer",
    "platform engineer",
}


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
    if "react native" in normalized:
        aliases.add("reactnative")
    return sorted(aliases)


def matches_role(title: str, tags: list[str] | None = None, roles: list[str] | None = None) -> bool:
    """Keep a raw feed item when its title or tags contain a target role/skill phrase."""
    if not roles:
        return True

    title_norm = _norm(title)
    title_tokens = set(title_norm.split())
    tag_text = _norm(" ".join(tags or []))

    # Adjacent engineering roles are always retained when their wording is explicit.
    for term in _ADJACENT_TITLE_TERMS:
        if re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", title_norm):
            return True

    for role in roles:
        for alias in _role_aliases(role):
            if not alias:
                continue
            if alias in title_norm:
                return True
            alias_tokens = set(alias.split())
            if alias_tokens and alias_tokens.issubset(title_tokens):
                return True
            # A profile skill/title appearing in tags keeps the item even when the
            # title itself is generic (recall over precision at prefilter time).
            if alias in tag_text:
                return True
    return False
