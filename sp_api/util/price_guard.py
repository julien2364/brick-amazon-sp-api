"""Garde-fou de prix avant tout envoi à Amazon (listings, feeds, prix et quantité).

Contexte : le 04/11/2026, les prix Amazon.pl ont été écrasés par un prix fixe par
catégorie multiplié par 100 (ex. 12 615 zł pour une trousse à ~29 €) : des centimes
envoyés comme des unités. Ce module calcule le prix d'un marché étranger à partir du
prix FR (règle du 27/10 : prix FR converti au taux BCE) et refuse tout prix aberrant.
"""
from decimal import Decimal, ROUND_HALF_UP

__all__ = ["PriceRejected", "foreign_price", "check_price"]

DEFAULT_FLOOR_EUR = Decimal("15")
MAX_RATIO = Decimal("3")


class PriceRejected(ValueError):
    """Prix refusé par le garde-fou : ne pas l'envoyer à Amazon."""


def _d(value):
    return Decimal(str(value))


def foreign_price(price_fr_eur, eur_rate, floor_eur=DEFAULT_FLOOR_EUR):
    """Prix dans la devise du marché (unités, pas centimes), arrondi au centime.

    prix = max(prix FR ; plancher) × taux EUR→devise.
    """
    fr, rate = _d(price_fr_eur), _d(eur_rate)
    if fr <= 0 or rate <= 0:
        raise PriceRejected("prix FR ou taux invalide")
    price = (max(fr, _d(floor_eur)) * rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
    check_price(price, fr, rate, floor_eur)
    return price


def check_price(price, reference_eur, eur_rate, floor_eur=DEFAULT_FLOOR_EUR, max_ratio=MAX_RATIO):
    """Lève PriceRejected si le prix est sous le plancher ou > max_ratio × la référence."""
    price, rate = _d(price), _d(eur_rate)
    floor = (_d(floor_eur) * rate).quantize(Decimal("0.01"), ROUND_HALF_UP)
    if price < floor:
        raise PriceRejected(f"{price} sous le plancher {floor}")
    reference = max(_d(reference_eur), _d(floor_eur)) * rate
    if price > reference * _d(max_ratio):
        raise PriceRejected(
            f"{price} > {max_ratio}× la référence {reference:.2f} (centimes envoyés comme unités ?)"
        )
    return price
