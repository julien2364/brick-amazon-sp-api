"""Garde-fou de prix avant tout envoi à Amazon (listings, feeds, prix et quantité).

Contexte : début novembre 2026, les prix Amazon.pl (A1C3SOZRARQ6R3) ont été écrasés
par un job non identifié, avec deux signatures :

* groupe « A_x100 » : prix ≈ 100 × le bon prix (12 615 zł au lieu de ~126 zł),
  des grosz envoyés comme des zł ;
* groupe « B_prix_fixe » : prix fixe de 150 zł par catégorie.

Règle validée (session du 05/11/2026) :
    prix PL = max(prix FR ; 15 €) × taux BCE EUR/PLN, en zł (jamais en grosz),
    arrondi au centime.
Garde-fou : refuser tout prix > 3 × la référence ou < au plancher de 66,06 zł.

Le module ne fait aucun appel réseau : il se branche juste avant
``patch_listings_item`` / ``put_listings_item`` / un feed de prix.
"""
from decimal import Decimal, ROUND_HALF_UP

__all__ = [
    "PriceRejected",
    "foreign_price",
    "check_price",
    "controler_prix",
    "prix_pl",
    "verifier_prix_pl",
    "classer_anomalie",
    "PLANCHER_PL_PLN",
    "PLANCHER_EUR",
    "RATIO_MAX",
]

PLANCHER_EUR = Decimal("15")
PLANCHER_PL_PLN = Decimal("66.06")  # 15 € × 4,404 (taux BCE retenu par la règle)
RATIO_MAX = Decimal("3")
PRIX_FIXE_SUSPECT_PLN = Decimal("150")
CENTIME = Decimal("0.01")

# Noms historiques (PR #1), conservés pour compatibilité.
DEFAULT_FLOOR_EUR = PLANCHER_EUR
MAX_RATIO = RATIO_MAX


class PriceRejected(ValueError):
    """Prix refusé par le garde-fou : ne pas l'envoyer à Amazon."""


def _d(value):
    if isinstance(value, bool):
        raise PriceRejected("valeur booléenne refusée")
    try:
        d = Decimal(str(value))
    except Exception as exc:  # noqa: BLE001 - toute entrée illisible est refusée
        raise PriceRejected(f"valeur illisible : {value!r}") from exc
    if not d.is_finite():
        raise PriceRejected(f"valeur non finie : {value!r}")
    return d


def _arrondi(value):
    return value.quantize(CENTIME, ROUND_HALF_UP)


def foreign_price(price_fr_eur, eur_rate, floor_eur=PLANCHER_EUR):
    """Prix de référence dans la devise du marché (unités, pas centimes), au centime.

    prix = max(prix FR ; plancher en €) × taux EUR→devise.
    """
    fr, rate = _d(price_fr_eur), _d(eur_rate)
    if fr <= 0 or rate <= 0:
        raise PriceRejected("prix FR ou taux invalide")
    return _arrondi(max(fr, _d(floor_eur)) * rate)


def controler_prix(prix, reference, plancher, ratio_max=RATIO_MAX):
    """Lève PriceRejected si ``prix`` < ``plancher`` ou > ``ratio_max`` × ``reference``.

    Toutes les valeurs sont dans la même devise (unités, pas centimes).
    Renvoie le prix arrondi au centime s'il est accepté.
    """
    prix, reference, plancher = _d(prix), _d(reference), _d(plancher)
    if reference <= 0:
        raise PriceRejected("référence invalide")
    if prix < plancher:
        raise PriceRejected(f"{prix} sous le plancher {plancher}")
    plafond = reference * _d(ratio_max)
    if prix > plafond:
        raise PriceRejected(
            f"{prix} > {ratio_max} × la référence {_arrondi(reference)} "
            "(centimes/grosz envoyés comme unités ?)"
        )
    return _arrondi(prix)


def check_price(price, reference_eur, eur_rate, floor_eur=PLANCHER_EUR, max_ratio=RATIO_MAX):
    """Variante générique (signature PR #1) : plancher = floor_eur × taux."""
    reference = foreign_price(reference_eur, eur_rate, floor_eur)
    floor = _arrondi(_d(floor_eur) * _d(eur_rate))
    return controler_prix(price, reference, floor, max_ratio)


def prix_pl(prix_fr_eur, taux_bce_eur_pln):
    """Prix Amazon.pl en zł selon la règle validée : max(prix FR ; 15 €) × taux BCE."""
    return foreign_price(prix_fr_eur, taux_bce_eur_pln, PLANCHER_EUR)


def verifier_prix_pl(prix_envoye_pln, prix_fr_eur, taux_bce_eur_pln,
                     plancher_pln=PLANCHER_PL_PLN, ratio_max=RATIO_MAX):
    """Dernier contrôle avant envoi d'un prix sur Amazon.pl.

    Refuse (PriceRejected) un prix > ``ratio_max`` × la référence ``prix_pl`` ou
    < ``plancher_pln`` (66,06 zł). Renvoie le prix accepté, arrondi au centime.
    """
    reference = prix_pl(prix_fr_eur, taux_bce_eur_pln)
    return controler_prix(prix_envoye_pln, reference, plancher_pln, ratio_max)


def classer_anomalie(prix_constate_pln, prix_fr_eur, taux_bce_eur_pln, tolerance=Decimal("0.05")):
    """Classe un prix constaté sur Amazon.pl : ``"A_x100"``, ``"B_prix_fixe"`` ou ``None``.

    Sert à auditer un rapport d'annonces, sans rien envoyer.
    """
    prix = _d(prix_constate_pln)
    reference = prix_pl(prix_fr_eur, taux_bce_eur_pln)
    if abs(prix / 100 - reference) <= reference * _d(tolerance):
        return "A_x100"
    if prix == PRIX_FIXE_SUSPECT_PLN and abs(prix - reference) > CENTIME:
        return "B_prix_fixe"
    return None
