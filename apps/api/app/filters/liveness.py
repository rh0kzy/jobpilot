"""Liveness checks for job pages."""

import httpx

CLOSED_PHRASES_EN = [
    "no longer accepting",
    "position has been filled",
    "job is closed",
    "this job is no longer available",
    "application is closed",
    "role has been filled",
]

CLOSED_PHRASES_FR = [
    "poste pourvu",
    "candidatures closes",
    "offre expiree",
    "offre expirée",
    "ce poste n'est plus disponible",
    "poste ferme",
    "poste fermé",
]

CLOSED_PHRASES_AR = [
    "تم شغل الوظيفة",
    "الوظيفة مغلقة",
    "انتهت صلاحية",
    "لا يتم قبول طلبات",
    "المنصب شاغل",
    "العرض منتهي",
]

# Flat, easy-to-extend list used by `is_live`.
CLOSED_PHRASES = CLOSED_PHRASES_EN + CLOSED_PHRASES_FR + CLOSED_PHRASES_AR


def register_closed_phrase(phrase: str) -> None:
    if phrase not in CLOSED_PHRASES:
        CLOSED_PHRASES.append(phrase)


def is_live(html: str) -> bool:
    text = (html or "").lower()
    return not any(phrase.lower() in text for phrase in CLOSED_PHRASES)


async def check_url(url: str, timeout: int = 30) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
    except Exception:  # noqa: BLE001
        return False
    if resp.status_code >= 400:
        return False
    return is_live(resp.text)