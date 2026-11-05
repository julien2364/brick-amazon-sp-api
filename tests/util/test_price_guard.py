from decimal import Decimal

import pytest

from sp_api.util.price_guard import (
    PLANCHER_PL_PLN,
    PriceRejected,
    check_price,
    classer_anomalie,
    foreign_price,
    prix_pl,
    verifier_prix_pl,
)

TAUX_PLN = Decimal("4.404")  # taux BCE EUR/PLN retenu par la règle (15 € × 4,404 = 66,06 zł)
RATE_PLN_0411 = 4.3990  # BCE, 04/11/2026 (tests de la PR #1)


# --- Règle : max(prix FR ; 15 €) × taux BCE, en zł, au centime -----------------

def test_regle_prix_pl_en_zl_pas_en_grosz():
    assert prix_pl("28.65", TAUX_PLN) == Decimal("126.17")


def test_regle_plancher_15_eur_donne_66_06_zl():
    assert prix_pl("9.99", TAUX_PLN) == PLANCHER_PL_PLN == Decimal("66.06")


def test_arrondi_au_centime_demi_superieur():
    # 15,005 € × 1 -> 15,01 (ROUND_HALF_UP)
    assert foreign_price("15.005", 1) == Decimal("15.01")


# --- Groupe A_x100 : le cas 12 615 zł doit être refusé ------------------------

def test_cas_12615_zl_refuse():
    with pytest.raises(PriceRejected, match="référence 126.17"):
        verifier_prix_pl(12615, "28.65", TAUX_PLN)


@pytest.mark.parametrize("prix_x100,prix_fr", [(12615, "28.65"), (14107, "32.03"), (14786, "33.57")])
def test_groupe_a_x100_refuse_et_classe(prix_x100, prix_fr):
    with pytest.raises(PriceRejected):
        verifier_prix_pl(prix_x100, prix_fr, TAUX_PLN)
    assert classer_anomalie(prix_x100, prix_fr, TAUX_PLN) == "A_x100"
    # Le même montant divisé par 100 (zł au lieu de grosz) passe.
    assert verifier_prix_pl(Decimal(prix_x100) / 100, prix_fr, TAUX_PLN) == Decimal(prix_x100) / 100


def test_prix_correct_accepte():
    assert verifier_prix_pl(prix_pl("28.65", TAUX_PLN), "28.65", TAUX_PLN) == Decimal("126.17")


def test_borne_3x_incluse_puis_refus():
    ref = prix_pl("28.65", TAUX_PLN)
    assert verifier_prix_pl(ref * 3, "28.65", TAUX_PLN) == Decimal("378.51")
    with pytest.raises(PriceRejected):
        verifier_prix_pl(ref * 3 + Decimal("0.01"), "28.65", TAUX_PLN)


# --- Plancher 66,06 zł ---------------------------------------------------------

def test_plancher_66_06_accepte_66_05_refuse():
    assert verifier_prix_pl("66.06", "9.99", TAUX_PLN) == Decimal("66.06")
    with pytest.raises(PriceRejected, match="plancher 66.06"):
        verifier_prix_pl("66.05", "9.99", TAUX_PLN)


def test_taux_en_baisse_bloque_plutot_que_brader():
    # Si le taux BCE passe sous 4,404, 15 € convertis tombent sous 66,06 zł : refus explicite.
    with pytest.raises(PriceRejected):
        verifier_prix_pl(prix_pl("9.99", "4.30"), "9.99", "4.30")


# --- Groupe B_prix_fixe : 150 zł ---------------------------------------------

def test_groupe_b_150_zl_detecte_par_classement():
    assert classer_anomalie(150, "12.00", TAUX_PLN) == "B_prix_fixe"
    assert classer_anomalie(150, "50.00", TAUX_PLN) == "B_prix_fixe"
    # 150 zł est légitime si la règle donne 150 zł.
    assert classer_anomalie(150, Decimal("150") / TAUX_PLN, TAUX_PLN) is None


def test_groupe_b_150_zl_passe_le_garde_fou_limite_connue():
    # 150 zł reste entre 66,06 zł et 3 × la référence : le garde-fou seul ne le bloque pas ;
    # c'est le recalcul par prix_pl() qui supprime le prix fixe (cf. HANDOFF, LIMITES).
    assert verifier_prix_pl(150, "12.00", TAUX_PLN) == Decimal("150.00")
    assert prix_pl("12.00", TAUX_PLN) == Decimal("66.06")


# --- Entrées invalides ---------------------------------------------------------

@pytest.mark.parametrize("valeur", [0, -1, "abc", "NaN", "Infinity", None, True])
def test_entrees_invalides_refusees(valeur):
    with pytest.raises(PriceRejected):
        verifier_prix_pl(100, valeur, TAUX_PLN)


# --- Compatibilité avec la signature de la PR #1 -------------------------------

def test_compat_pr1_foreign_price_et_check_price():
    assert foreign_price(29.70, RATE_PLN_0411) == Decimal("130.65")
    assert foreign_price(9.99, RATE_PLN_0411) == Decimal("65.99")
    with pytest.raises(PriceRejected):
        check_price(12615, 29.70, RATE_PLN_0411)
    with pytest.raises(PriceRejected):
        check_price(10, 9.0, RATE_PLN_0411)
