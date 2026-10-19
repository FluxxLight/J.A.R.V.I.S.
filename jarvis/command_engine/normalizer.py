"""Normalização robusta de texto (etapa obrigatória antes do matching).

- minúsculas, sem acentos, sem pontuação, espaços colapsados
- lematização de verbos de comando em pt-BR ("abre"/"abra" -> "abrir"),
  para que conjugações diferentes da mesma ordem convirjam
- preserva palavras importantes (não remove stopwords aqui)
"""

from __future__ import annotations

import re

from jarvis.utils.text import collapse_spaces, remove_punctuation, safe_lower, strip_accents

_FILLER_RE = re.compile(
    r"^(por favor|por gentileza|por obsequio|por obséquio)\s+|\s+(por favor|por gentileza)\s*$"
)

# verbo no infinitivo -> conjugações/variações que convergem para ele.
# ATENÇÃO: "para" NÃO está aqui (é preposição em "deixa para lá").
_VERB_LEMMAS: dict[str, set[str]] = {
    "abrir": {"abra", "abre", "abram", "abrindo", "aberto", "aberta"},
    "fechar": {"feche", "fecha", "fechem", "fechando", "fechado"},
    "iniciar": {"inicie", "inicia", "iniciem", "iniciando"},
    "executar": {"execute", "executa", "executem", "executando"},
    "rodar": {"rode", "roda", "rodem"},
    "lancar": {"lance", "lanca", "lancem"},
    "minimizar": {"minimize", "minimiza", "minimizem"},
    "maximizar": {"maximize", "maximiza", "maximizem"},
    "bloquear": {"bloqueie", "bloqueia", "bloqueiem"},
    "reiniciar": {"reinicie", "reinicia", "reiniciem"},
    "desligar": {"desligue", "desliga", "desliguem", "desligando"},
    "ligar": {"ligue", "liga", "liguem"},
    "travar": {"trave", "trava", "travem"},
    "mostrar": {"mostre", "mostra", "mostrem"},
    "dizer": {"diga", "dizem", "dizendo", "dito"},
    "falar": {"fale", "fala", "falem", "falando"},
    "colocar": {"coloque", "coloca", "coloquem"},
    "acessar": {"acesse", "acessa", "acessem"},
    "cancelar": {"cancele", "cancela", "cancelem"},
    "confirmar": {"confirme", "confirma", "confirmem", "confirmo", "confirmado"},
    "repetir": {"repita", "repete"},
    "alternar": {"alterne", "alterna"},
    "parar": {"pare"},
    "abortar": {"aborta", "aborte"},
    "esquecer": {"esquece"},
    "prosseguir": {"prossiga"},
    "ocultar": {"oculte", "oculta"},
    "expandir": {"expanda"},
    "restaurar": {"restaure"},
}

_INFLECTION_TO_LEMMA: dict[str, str] = {}
for _lemma, _forms in _VERB_LEMMAS.items():
    for _form in _forms:
        _INFLECTION_TO_LEMMA[_form] = _lemma


def lemmatize_verbs(normalized: str) -> str:
    """Troca conjugações conhecidas pelo infinitivo (por token exato)."""
    if not normalized:
        return ""
    return " ".join(_INFLECTION_TO_LEMMA.get(tok, tok) for tok in normalized.split())


def normalize(text: str | None) -> str:
    """Normaliza texto para comparação determinística. Nunca levanta exceção."""
    if not text:
        return ""
    try:
        out = safe_lower(str(text))
        out = strip_accents(out)
        out = remove_punctuation(out)
        out = collapse_spaces(out)
        out = _FILLER_RE.sub(" ", out)
        out = collapse_spaces(out)
        out = lemmatize_verbs(out)
        return out
    except Exception:
        return ""


def normalize_keep_url_chars(text: str | None) -> str:
    """Variação que preserva caracteres de URL (para extração de entidades)."""
    if not text:
        return ""
    try:
        out = safe_lower(str(text))
        out = remove_punctuation(out, keep="/.:@-")
        return collapse_spaces(out)
    except Exception:
        return ""
