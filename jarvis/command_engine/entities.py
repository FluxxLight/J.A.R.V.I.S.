"""Extração de entidades/parâmetros por regras (URLs, apps, texto livre)."""

from __future__ import annotations

import re
from typing import Any, Optional

from jarvis.system import launcher

_OPEN_VERBS = {"abra", "abrir", "abre", "abram", "inicie", "inicia", "iniciar",
               "execute", "executa", "executar", "rode", "rodar", "lance", "lancar",
               "acesse", "acessa", "acessar"}
_NOISE_WORDS = {"o", "a", "os", "as", "um", "uma", "meu", "minha", "meus", "minhas",
                "esse", "essa", "este", "esta", "aquele", "aquela", "ai", "aí",
                "por", "favor", "pra", "para", "mim", "agora", "ja", "já",
                "site", "pagina", "página", "link", "url", "programa", "aplicativo",
                "app", "navegador", "browser"}

_QUOTED_RE = re.compile(r'"([^"]+)"|\'([^\']+)\'')


def extract_url(raw_text: str) -> Optional[str]:
    return launcher.extract_url(raw_text or "")


def extract_quoted(raw_text: str) -> Optional[str]:
    match = _QUOTED_RE.search(raw_text or "")
    if not match:
        return None
    return (match.group(1) or match.group(2) or "").strip() or None


def extract_app_name(normalized: str) -> Optional[str]:
    """Extrai nome de app após verbo de abertura. Ex.: 'abra o discord' -> 'discord'."""
    tokens = (normalized or "").split()
    if not tokens:
        return None
    # remove verbo inicial se houver
    start = 1 if tokens[0] in _OPEN_VERBS else 0
    rest = [t for t in tokens[start:] if t not in _NOISE_WORDS]
    if not rest:
        return None
    candidate = " ".join(rest).strip()
    # evita frases longas: app costuma ter 1-2 palavras
    words = candidate.split()
    if len(words) > 3:
        return None
    return candidate or None


def extract_site_query(normalized: str) -> Optional[str]:
    """Extrai 'youtube' de 'abra o youtube' (para abrir como URL conhecida/busca)."""
    return extract_app_name(normalized)


def build_params(intent: str, raw_text: str, normalized: str,
                 base_params: dict[str, Any]) -> dict[str, Any]:
    """Mescla parâmetros do comando com entidades extraídas da frase."""
    params = dict(base_params or {})
    if intent == "OPEN_URL":
        url = extract_url(raw_text)
        quoted = extract_quoted(raw_text)
        if url:
            params["url"] = url
        elif quoted and ("." in quoted or quoted.startswith("http")):
            candidate = quoted if quoted.startswith("http") else "http://" + quoted
            if launcher.is_valid_url(candidate):
                params["url"] = candidate
        elif "url" not in params or not params["url"]:
            query = extract_site_query(normalized)
            if query:
                # sites conhecidos -> URL direta; senão busca no Google
                known = _known_site(query)
                params["url"] = known or (
                    "https://www.google.com/search?q=" + query.replace(" ", "+"))
    elif intent == "OPEN_APP":
        app = extract_app_name(normalized)
        if app and not params.get("app"):
            params["app"] = app
    return params


_KNOWN_SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://www.twitter.com",
    "x": "https://www.x.com",
    "github": "https://www.github.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "whatsapp": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
    "linkedin": "https://www.linkedin.com",
    "twitch": "https://www.twitch.tv",
}


def _known_site(query: str) -> Optional[str]:
    key = (query or "").strip().lower()
    if key in _KNOWN_SITES:
        return _KNOWN_SITES[key]
    # "youtube com" / "site youtube" -> pega a palavra conhecida
    for word in key.split():
        if word in _KNOWN_SITES:
            return _KNOWN_SITES[word]
    return None


def detect_url_intent(raw_text: str, normalized: str) -> Optional[dict[str, Any]]:
    """Regra determinística de alta precisão para OPEN_URL.

    Dispara quando:
    - há URL literal na frase ("abra o site https://..."); ou
    - verbo de abertura + site conhecido ("abra o youtube").
    Retorna params {"url": ...} ou None.
    """
    url = extract_url(raw_text or "")
    if url:
        return {"url": url}
    tokens = (normalized or "").split()
    if tokens and tokens[0] in _OPEN_VERBS:
        rest = [t for t in tokens[1:] if t not in _NOISE_WORDS]
        known = _known_site(" ".join(rest))
        if known:
            return {"url": known}
    return None
