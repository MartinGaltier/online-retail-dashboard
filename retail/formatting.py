"""Mise en forme des nombres à la française (espace fine insécable comme séparateur de milliers)."""

from __future__ import annotations

import math

NARROW_NBSP = " "
MISSING = "—"


def _is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def number(value, decimals: int = 0) -> str:
    if _is_missing(value):
        return MISSING
    text = f"{value:,.{decimals}f}"
    return text.replace(",", NARROW_NBSP).replace(".", ",")


def money(value, decimals: int = 0) -> str:
    if _is_missing(value):
        return MISSING
    return f"{number(value, decimals)}{NARROW_NBSP}£"


def compact_money(value) -> str:
    """Montant abrégé pour les cartes d'indicateurs : 9,96 M£ ; 504 k£ ; 950 £."""
    if _is_missing(value):
        return MISSING
    magnitude = abs(value)
    if magnitude >= 1_000_000:
        return f"{number(value / 1_000_000, 2)}{NARROW_NBSP}M£"
    if magnitude >= 10_000:
        return f"{number(value / 1_000, 0)}{NARROW_NBSP}k£"
    return money(value)


def percent(value, decimals: int = 1) -> str:
    """`value` est une proportion (0,25 → « 25,0 % »)."""
    if _is_missing(value):
        return MISSING
    return f"{number(value * 100, decimals)}{NARROW_NBSP}%"


def signed_percent(value, decimals: int = 1) -> str:
    if _is_missing(value):
        return MISSING
    sign = "+" if value > 0 else ""
    return f"{sign}{percent(value, decimals)}"


def relative_change(current, previous):
    """Variation relative ; None si la valeur précédente est absente ou nulle."""
    if _is_missing(current) or _is_missing(previous) or previous == 0:
        return None
    return current / previous - 1


def date_fr(value) -> str:
    return value.strftime("%d/%m/%Y")


MONTHS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def month_fr(value) -> str:
    return f"{MONTHS_FR[value.month - 1]} {value.year}"
