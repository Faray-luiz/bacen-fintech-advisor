"""Deterministic domain normalizers for Brazilian financial institutions, segments and credit modalities."""

from __future__ import annotations

import re
import unicodedata

INSTITUTION_MAP: dict[str, str] = {
    "NUBANK": "NUBANK",
    "NU": "NUBANK",
    "NU PAGAMENTOS": "NUBANK",
    "NU HOLDINGS": "NUBANK",
    "NU FINANCEIRA": "NUBANK",
    "ITAU": "ITAU",
    "ITAU UNIBANCO": "ITAU",
    "ITAUCARD": "ITAU",
    "BRADESCO": "BRADESCO",
    "BCO BRADESCO": "BRADESCO",
    "BANCO DO BRASIL": "BANCO_DO_BRASIL",
    "BANCO_DO_BRASIL": "BANCO_DO_BRASIL",
    "BCO DO BRASIL": "BANCO_DO_BRASIL",
    "BB": "BANCO_DO_BRASIL",
    "SANTANDER": "SANTANDER",
    "BCO SANTANDER": "SANTANDER",
    "CAIXA": "CAIXA",
    "CEF": "CAIXA",
    "CAIXA ECONOMICA FEDERAL": "CAIXA",
    "INTER": "INTER",
    "BANCO INTER": "INTER",
    "C6": "C6_BANK",
    "C6 BANK": "C6_BANK",
    "C6_BANK": "C6_BANK",
    "BANCO C6": "C6_BANK",
    "MERCADO PAGO": "MERCADO_PAGO",
    "MERCADO_PAGO": "MERCADO_PAGO",
    "MP": "MERCADO_PAGO",
    "BTG": "BTG_PACTUAL",
    "BTG PACTUAL": "BTG_PACTUAL",
    "BTG_PACTUAL": "BTG_PACTUAL",
}

SEGMENT_MAP: dict[str, str] = {
    "TODOS": "TODOS",
    "ALL": "TODOS",
    "GERAL": "TODOS",
    "MERCADO": "TODOS",
    "NEOBANKS": "NEOBANKS",
    "NEOBANK": "NEOBANKS",
    "DIGITAIS": "NEOBANKS",
    "BANCOS DIGITAIS": "NEOBANKS",
    "FINTECHS": "NEOBANKS",
    "INCUMBENTES": "INCUMBENTES",
    "INCUMBENTE": "INCUMBENTES",
    "TRADICIONAIS": "INCUMBENTES",
    "GRANDES BANCOS": "INCUMBENTES",
    "BANCOS TRADICIONAIS": "INCUMBENTES",
    "S1": "INCUMBENTES",
}

CREDIT_MODALITY_MAP: dict[str, str] = {
    "CARTAO_ROTATIVO": "CARTAO_ROTATIVO",
    "ROTATIVO": "CARTAO_ROTATIVO",
    "CARTAO DE CREDITO ROTATIVO": "CARTAO_ROTATIVO",
    "CARTAO DE CREDITO - ROTATIVO TOTAL": "CARTAO_ROTATIVO",
    "ROTATIVO CARTAO": "CARTAO_ROTATIVO",
    "CREDITO_PESSOAL_NAO_CONSIGNADO": "CREDITO_PESSOAL_NAO_CONSIGNADO",
    "CREDITO PESSOAL": "CREDITO_PESSOAL_NAO_CONSIGNADO",
    "CREDITO PESSOAL NAO CONSIGNADO": "CREDITO_PESSOAL_NAO_CONSIGNADO",
    "EMPRESTIMO PESSOAL": "CREDITO_PESSOAL_NAO_CONSIGNADO",
    "CONSIGNADO_PRIVADO": "CONSIGNADO_PRIVADO",
    "CONSIGNADO": "CONSIGNADO_PRIVADO",
    "CREDITO PESSOAL CONSIGNADO PRIVADO": "CONSIGNADO_PRIVADO",
    "CREDITO CONSIGNADO": "CONSIGNADO_PRIVADO",
    "CHEQUE_ESPECIAL": "CHEQUE_ESPECIAL",
    "CHEQUE ESPECIAL": "CHEQUE_ESPECIAL",
    "PARCELADO_CARTAO": "PARCELADO_CARTAO",
    "CARTAO PARCELADO": "PARCELADO_CARTAO",
    "CARTAO DE CREDITO - PARCELADO": "PARCELADO_CARTAO",
    "PARCELADO CARTAO": "PARCELADO_CARTAO",
}


def _strip_accents_upper(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text.strip().upper())


def normalize_institution(value: str | None) -> str | None:
    """Normalizes free-text Brazilian institution names to canonical identifiers."""
    if not value or not value.strip():
        return None
    key = _strip_accents_upper(value)
    if key in INSTITUTION_MAP:
        return INSTITUTION_MAP[key]
    for alias, canonical in INSTITUTION_MAP.items():
        if alias in key:
            return canonical
    return key.replace(" ", "_")


def normalize_segment(value: str | None) -> str | None:
    """Normalizes market segment labels to ``TODOS``, ``NEOBANKS`` or ``INCUMBENTES``."""
    if not value or not value.strip():
        return None
    key = _strip_accents_upper(value)
    return SEGMENT_MAP.get(key, key)


def normalize_credit_modality(value: str | None) -> str | None:
    """Normalizes free-text credit modalities to canonical BCB Olinda keys."""
    if not value or not value.strip():
        return None
    key = _strip_accents_upper(value)
    if key in CREDIT_MODALITY_MAP:
        return CREDIT_MODALITY_MAP[key]
    for alias, canonical in CREDIT_MODALITY_MAP.items():
        if alias in key:
            return canonical
    return key.replace(" ", "_")
