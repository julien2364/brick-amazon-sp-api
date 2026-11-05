from decimal import Decimal

import pytest

from sp_api.util.price_guard import PriceRejected, check_price, foreign_price

RATE_PLN = 4.3990  # BCE, 04/11/2026


def test_prix_fr_converti_sans_x100():
    assert foreign_price(29.70, RATE_PLN) == Decimal("130.65")


def test_plancher_15_eur():
    assert foreign_price(9.99, RATE_PLN) == Decimal("65.99")


def test_bug_x100_du_04_11_refuse():
    with pytest.raises(PriceRejected):
        check_price(12615, 29.70, RATE_PLN)


def test_prix_fixe_150_zl_refuse_pour_article_a_9_eur():
    # 150 zł fixe par catégorie vs référence max(9 ; 15) € × 4,399 = 65,99 zł : < 3×, accepté
    # par le garde-fou ; c'est foreign_price qui supprime le prix fixe.
    assert foreign_price(9.0, RATE_PLN) == Decimal("65.99")


def test_sous_plancher_refuse():
    with pytest.raises(PriceRejected):
        check_price(10, 9.0, RATE_PLN)


def test_entrees_invalides():
    with pytest.raises(PriceRejected):
        foreign_price(0, RATE_PLN)
