"""Portfolio pulse: activity and freshness of my own public GitHub repos.

Reads the dbt marts that the daily workflow publishes as parquet.
"""

from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

MARTS = Path(__file__).parent / "data" / "marts"

# Fixed layer -> hue, assigned once: a filter must never repaint a series.
# Slots 1-5 of the reference categorical palette, dark steps (validator: PASS).
LAYER_COLORS = {
    "data": "#3987e5",
    "web": "#d95926",
    "learning": "#199e70",
    "vault": "#c98500",
    "other": "#d55181",
}
BLUE = "#3987e5"
CHART = {
    "template": None,
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"color": "#c3c2b7"},
    "margin": {"l": 0, "r": 0, "t": 10, "b": 0},
}


@st.cache_data(ttl=3600)
def load(name: str) -> pd.DataFrame:
    return duckdb.sql(f"select * from read_parquet('{MARTS / name}.parquet')").df()


st.set_page_config(page_title="Portfolio pulse", layout="wide")
st.title("Portfolio pulse")
st.caption(
    "Мой публичный GitHub: что живое, что затихло, куда уходит время. "
    "Данные обновляются раз в сутки через GitHub Actions."
)

if not (MARTS / "fct_portfolio_health.parquet").exists():
    st.error("Нет `data/marts/*.parquet`. Запусти `make all` или дождись workflow.")
    st.stop()

health = load("fct_portfolio_health")
weekly = load("fct_activity_weekly")
layers = load("fct_layer_activity")

kpi = st.columns(4)
kpi[0].metric("Репозиториев", len(health))
kpi[1].metric("Живых (≤90 дней)", int((health["status"] == "active").sum()))
kpi[2].metric("Звёзд", int(health["stars"].sum()))
kpi[3].metric("Контрибуций за год", int(weekly["contributions"].sum()))

filters = st.columns([1, 2])
picked_layers = filters[0].multiselect(
    "Слой", sorted(health["layer"].unique()), default=sorted(health["layer"].unique())
)
statuses = ["active", "quiet", "dormant", "archived"]
picked_statuses = filters[1].multiselect("Статус", statuses, default=statuses)

view = health[health["layer"].isin(picked_layers) & health["status"].isin(picked_statuses)]

st.subheader("Свежесть портфеля")
st.dataframe(
    view[
        [
            "repo_name",
            "layer",
            "status",
            "days_since_push",
            "commits_90d",
            "commits_12mo",
            "stars",
            "language",
            "last_pushed_on",
        ]
    ].sort_values(["commits_90d", "stars"], ascending=False),
    hide_index=True,
    width="stretch",
    column_config={
        "repo_name": "Проект",
        "layer": "Слой",
        "status": "Статус",
        "days_since_push": st.column_config.NumberColumn("Дней с пуша"),
        "commits_90d": st.column_config.NumberColumn("Коммитов 90д"),
        "commits_12mo": st.column_config.NumberColumn("Коммитов 12м"),
        "stars": st.column_config.NumberColumn("★"),
        "language": "Язык",
        "last_pushed_on": "Последний пуш",
    },
)

charts = st.columns(2)

with charts[0]:
    st.subheader("Активность по неделям")
    fig = px.bar(weekly, x="week_start", y="contributions")
    fig.update_traces(marker_color=BLUE, marker_line_width=0)
    fig.update_layout(
        **CHART,
        height=280,
        xaxis_title=None,
        yaxis_title="Контрибуций",
        bargap=0.25,
    )
    st.plotly_chart(fig, width="stretch")

with charts[1]:
    st.subheader("Куда уходит время (90 дней)")
    bar = px.bar(
        layers.sort_values("commits_90d"),
        x="commits_90d",
        y="layer",
        orientation="h",
        color="layer",
        color_discrete_map=LAYER_COLORS,
        text="commits_90d",
    )
    bar.update_traces(marker_line_width=0, textposition="outside")
    bar.update_layout(
        **CHART,
        height=280,
        showlegend=False,
        xaxis_title=None,
        yaxis_title=None,
    )
    st.plotly_chart(bar, width="stretch")

with st.expander("Данные под графиками"):
    st.dataframe(layers, hide_index=True, width="stretch")
    st.dataframe(weekly, hide_index=True, width="stretch")
