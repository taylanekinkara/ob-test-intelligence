from __future__ import annotations

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "bus": ["bus", "journey", "sefer", "biniş"],
    "flight": ["flight", "ucak", "hava"],
    "hotel": ["hotel", "otel", "konaklama"],
    "sea": ["sea", "deniz", "ferry", "vapur"],
    "payment": ["payment", "odeme", "pos", "refund", "kupony"],
    "rentacar": ["rentacar", "rent", "araç"],
    "transfer": ["transfer"],
}


def classify_domain(file_path: str, content: str = "") -> str:
    text = (file_path + " " + content).lower().replace("\\", "/")
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return domain
    return "unknown"


def classify_domains(file_paths: list[str], contents: dict[str, str] | None = None) -> list[str]:
    domains = set()
    contents = contents or {}
    for fp in file_paths:
        domains.add(classify_domain(fp, contents.get(fp, "")))
    domains.discard("unknown")
    return sorted(domains)
