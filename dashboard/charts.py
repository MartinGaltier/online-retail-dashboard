"""Graphiques Plotly de l'application.

Fonctions pures : elles reçoivent des DataFrames déjà agrégés et renvoient une figure, ce qui
permet de les tester sans lancer Streamlit. Les valeurs affichées dans les infobulles sont
préformatées en français (séparateur de milliers, virgule décimale, symbole £).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from retail import formatting as fmt
from retail.queries import period_end

# Palette catégorielle validée (contraste et daltonisme) : bleu, puis orange.
SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"
NEUTRAL = "#9a9890"
GRID = "rgba(128, 128, 128, 0.18)"

PERIOD_LABELS = {"day": "jour", "week": "semaine", "month": "mois"}


def _period_label(start: pd.Timestamp, grain: str) -> str:
    if grain == "month":
        return fmt.month_fr(start)
    if grain == "week":
        return f"semaine du {fmt.date_fr(start)}"
    return fmt.date_fr(start)


def _base_layout(fig: go.Figure, title: str, y_title: str, height: int = 380) -> go.Figure:
    fig.update_layout(
        title={"text": title, "x": 0, "xanchor": "left", "font": {"size": 16}},
        height=height,
        margin={"l": 8, "r": 8, "t": 56, "b": 8},
        separators=", ",
        hoverlabel={"namelength": -1},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.0, "xanchor": "right", "x": 1},
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(title_text=y_title, gridcolor=GRID, zeroline=True, zerolinecolor=GRID,
                     rangemode="tozero")
    return fig


def _date_axis(fig: go.Figure, grain: str) -> None:
    # Formats numériques : les noms de mois de Plotly seraient en anglais.
    fig.update_xaxes(tickformat="%m/%Y" if grain == "month" else "%d/%m/%Y")


def _shade_partial_periods(fig: go.Figure, trend: pd.DataFrame, grain: str) -> None:
    """Grise les périodes incomplètes pour éviter de les comparer aux autres."""
    for start in trend.loc[trend["is_partial"], "period_start"]:
        end = period_end(start, grain) + pd.Timedelta(days=1)
        if grain == "month":
            x0, x1 = start - pd.Timedelta(days=14), start + pd.Timedelta(days=14)
        elif grain == "week":
            x0, x1 = start - pd.Timedelta(days=3), start + pd.Timedelta(days=4)
        else:
            x0, x1 = start - pd.Timedelta(hours=12), end - pd.Timedelta(hours=12)
        fig.add_vrect(
            x0=x0, x1=x1, fillcolor=NEUTRAL, opacity=0.15, line_width=0, layer="below",
            annotation_text="incomplet", annotation_position="top left",
            annotation_font_size=11, annotation_font_color=NEUTRAL,
        )


def sales_trend_figure(trend: pd.DataFrame, grain: str) -> go.Figure:
    labels = [_period_label(p, grain) for p in trend["period_start"]]
    partial = ["  (période incomplète)" if flag else "" for flag in trend["is_partial"]]
    custom = list(zip(
        labels,
        [fmt.money(v) for v in trend["gross_sales"]],
        [fmt.money(v) for v in trend["net_sales"]],
        [fmt.number(v) for v in trend["orders"]],
        partial, strict=True,
    ))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trend["period_start"], y=trend["gross_sales"], name="CA des ventes",
        mode="lines+markers", line={"color": SERIES_1, "width": 2}, marker={"size": 6},
        customdata=custom,
        hovertemplate="<b>%{customdata[1]}</b> CA des ventes<br>"
                      "%{customdata[0]}%{customdata[4]}<br>%{customdata[3]} commandes<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=trend["period_start"], y=trend["net_sales"], name="CA net (après annulations)",
        mode="lines+markers", line={"color": SERIES_2, "width": 2}, marker={"size": 6},
        customdata=custom,
        hovertemplate="<b>%{customdata[2]}</b> CA net<extra></extra>",
    ))
    _shade_partial_periods(fig, trend, grain)
    _base_layout(fig, f"CA des ventes et CA net par {PERIOD_LABELS[grain]} (£)", "Montant (£)")
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(hoverformat=" ")
    _date_axis(fig, grain)
    return fig


def cancellations_figure(trend: pd.DataFrame, grain: str) -> go.Figure:
    labels = [_period_label(p, grain) for p in trend["period_start"]]
    ratio = trend["cancellations_amount"] / trend["gross_sales"].where(trend["gross_sales"] != 0)
    custom = list(zip(
        labels,
        [fmt.money(v) for v in trend["cancellations_amount"]],
        [fmt.percent(v) for v in ratio],
        ["  (période incomplète)" if flag else "" for flag in trend["is_partial"]], strict=True,
    ))
    fig = go.Figure(go.Bar(
        x=trend["period_start"], y=trend["cancellations_amount"], name="Annulations",
        marker={"color": SERIES_2, "cornerradius": 4}, customdata=custom,
        hovertemplate="<b>%{customdata[1]}</b> d'annulations enregistrées<br>"
                      "%{customdata[0]}%{customdata[3]}<br>"
                      "soit %{customdata[2]} du CA des ventes de la période<extra></extra>",
    ))
    _shade_partial_periods(fig, trend, grain)
    _base_layout(
        fig, f"Annulations et retours enregistrés par {PERIOD_LABELS[grain]} (£)", "Montant (£)",
        height=300,
    )
    _date_axis(fig, grain)
    return fig


def ranking_figure(
    frame: pd.DataFrame, label_column: str, value_column: str, title: str, value_kind: str,
    detail_column: str | None = None, detail_label: str = "",
) -> go.Figure:
    """Barres horizontales triées, la plus grande en haut. `value_kind` : 'money' ou 'number'."""
    frame = frame.iloc[::-1]
    formatter = fmt.money if value_kind == "money" else fmt.number
    values = [formatter(v) for v in frame[value_column]]
    details = (
        [f"<br>{detail_label} : {fmt.percent(v)}" for v in frame[detail_column]]
        if detail_column else [""] * len(frame)
    )
    labels = [text if len(text) <= 38 else text[:36] + "…" for text in frame[label_column]]
    fig = go.Figure(go.Bar(
        x=frame[value_column], y=labels, orientation="h",
        marker={"color": SERIES_1, "cornerradius": 4},
        customdata=list(zip(frame[label_column], values, details, strict=True)),
        hovertemplate="<b>%{customdata[1]}</b><br>%{customdata[0]}%{customdata[2]}<extra></extra>",
        text=values, textposition="outside", cliponaxis=False,
        textfont={"size": 11},
    ))
    height = max(260, 28 * len(frame) + 90)
    _base_layout(fig, title, "", height=height)
    fig.update_yaxes(title_text=None, gridcolor="rgba(0,0,0,0)", automargin=True)
    fig.update_xaxes(showgrid=False, showticklabels=False)
    fig.update_layout(margin={"l": 8, "r": 70, "t": 56, "b": 8})
    return fig


def frequency_figure(frequency: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for column, name, color in (
        ("customer_share", "Part des clients identifiés", SERIES_1),
        ("sales_share", "Part du CA des ventes de ces clients", SERIES_2),
    ):
        values = [fmt.percent(v) for v in frequency[column]]
        fig.add_trace(go.Bar(
            x=frequency["frequency_band"], y=frequency[column] * 100, name=name,
            marker={"color": color, "cornerradius": 4},
            customdata=list(zip(values, frequency["frequency_band"],
                                [fmt.number(v) for v in frequency["customers"]], strict=True)),
            hovertemplate=f"<b>%{{customdata[0]}}</b> {name.lower()}<br>"
                          "Clients ayant passé %{customdata[1]} (%{customdata[2]} clients)<extra></extra>",
        ))
    _base_layout(fig, "Clients identifiés et CA des ventes selon le nombre de commandes (%)",
                 "Part (%)")
    fig.update_layout(barmode="group", bargroupgap=0.08)
    return fig
