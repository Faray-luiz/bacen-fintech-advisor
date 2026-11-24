"""Unit tests for Bacen MCP domain normalizers."""

import pytest
from src.domain.normalizer import (
    normalize_credit_modality,
    normalize_institution,
    normalize_segment,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Nu Pagamentos", "NUBANK"),
        ("nubank", "NUBANK"),
        ("Itaú Unibanco", "ITAU"),
        ("BB", "BANCO_DO_BRASIL"),
        ("Banco Inter", "INTER"),
        ("C6 Bank", "C6_BANK"),
        ("Mercado Pago", "MERCADO_PAGO"),
        ("BTG Pactual", "BTG_PACTUAL"),
    ],
)
def test_normalize_institution(raw: str, expected: str) -> None:
    assert normalize_institution(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("bancos digitais", "NEOBANKS"),
        ("fintechs", "NEOBANKS"),
        ("grandes bancos", "INCUMBENTES"),
        ("S1", "INCUMBENTES"),
        ("todos", "TODOS"),
    ],
)
def test_normalize_segment(raw: str, expected: str) -> None:
    assert normalize_segment(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("rotativo", "CARTAO_ROTATIVO"),
        ("Cartão de crédito - rotativo total", "CARTAO_ROTATIVO"),
        ("crédito pessoal", "CREDITO_PESSOAL_NAO_CONSIGNADO"),
        ("consignado", "CONSIGNADO_PRIVADO"),
    ],
)
def test_normalize_credit_modality(raw: str, expected: str) -> None:
    assert normalize_credit_modality(raw) == expected
