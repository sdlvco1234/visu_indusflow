"""
Dashboard DPE — Analyse de la performance énergétique des logements
=====================================================================
Reprend et met en interface (Streamlit) le script d'analyse exploratoire
(consommation, DPE, qualité d'isolation, émissions) avec des filtres
globaux et 4 onglets thématiques.

Lancer avec :  streamlit run app.py
"""

import os
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ----------------------------------------------------------------------------
# Configuration générale de la page
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard DPE — Performance énergétique",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

COLORS_DPE = {
    "A": "#00A651",
    "B": "#99D18F",
    "C": "#FFD966",
    "D": "#F4B183",
    "E": "#ED7D31",
    "F": "#C00000",
    "G": "#7F6000",
}
ORDRE_DPE = ["A", "B", "C", "D", "E", "F", "G"]

DEFAULT_DB_PATH = "data/data.db"


# ----------------------------------------------------------------------------
# Chargement des données (mis en cache pour éviter de relire la base à
# chaque interaction)
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner="Chargement des données…")
def load_data(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        batiment = pd.read_sql_query("SELECT * FROM batiment", conn)
        consommation = pd.read_sql_query("SELECT * FROM consommation", conn)
        qualite = pd.read_sql_query("SELECT * FROM qualite", conn)
        emission = pd.read_sql_query("SELECT * FROM emmission", conn)
    finally:
        conn.close()
    return batiment, consommation, qualite, emission


@st.cache_data(show_spinner=False)
def build_conso_bat(batiment: pd.DataFrame, consommation: pd.DataFrame, tarif_eur_mwh: float):
    conso_bat = consommation[
        ["consommation_annuelle_moyenne_par_site_de_ladresse_mwh", "numero_dpe", "etiquette_dpe"]
    ].merge(
        batiment[["numero_dpe", "type_batiment", "surface_habitable_logement", "annee_construction"]],
        on="numero_dpe",
        how="left",
    )
    conso_bat["conso_ratio_surface"] = (
        conso_bat["consommation_annuelle_moyenne_par_site_de_ladresse_mwh"]
        / conso_bat["surface_habitable_logement"]
    )
    conso_bat["facture_annuelle_moyenne_euro"] = (
        conso_bat["consommation_annuelle_moyenne_par_site_de_ladresse_mwh"] * tarif_eur_mwh
    )
    conso_bat["facture_annuelle_par_m2"] = (
        conso_bat["facture_annuelle_moyenne_euro"] / conso_bat["surface_habitable_logement"]
    )
    return conso_bat


@st.cache_data(show_spinner=False)
def build_conso_ener(batiment: pd.DataFrame, consommation: pd.DataFrame):
    cols_conso = [
        "consommation_annuelle_moyenne_par_site_de_ladresse_mwh",
        "numero_dpe",
        "etiquette_dpe",
        "conso_chauffage_ef",
        "conso_refroidissement_ef",
        "conso_eclairage_ef",
    ]
    conso_bat_ener = consommation[cols_conso].merge(
        batiment[["numero_dpe", "type_energie_n1", "type_batiment", "surface_habitable_logement"]],
        on="numero_dpe",
        how="left",
    )
    conso_bat_ener["conso_chauffage_par_m2_ef"] = (
        conso_bat_ener["conso_chauffage_ef"] / conso_bat_ener["surface_habitable_logement"]
    )
    conso_bat_ener["conso_refroidissement_par_m2_ef"] = (
        conso_bat_ener["conso_refroidissement_ef"] / conso_bat_ener["surface_habitable_logement"]
    )
    conso_bat_ener["conso_eclairage_par_m2_ef"] = (
        conso_bat_ener["conso_eclairage_ef"] / conso_bat_ener["surface_habitable_logement"]
    )
    return conso_bat_ener


def kpi_card(col, label, value, help_text=None):
    col.metric(label, value, help=help_text)


def apply_filters(df, dpe_selected, type_selected, id_col="numero_dpe", dpe_col="etiquette_dpe", type_col=None):
    out = df.copy()
    if dpe_col in out.columns and dpe_selected:
        out = out[out[dpe_col].isin(dpe_selected)]
    if type_col and type_col in out.columns and type_selected:
        out = out[out[type_col].isin(type_selected)]
    return out


# ----------------------------------------------------------------------------
# Sidebar — source des données + filtres globaux
# ----------------------------------------------------------------------------
st.sidebar.title("🏠 Dashboard DPE")
st.sidebar.caption("Analyse de la performance énergétique des logements")

st.sidebar.subheader("📂 Source des données")
uploaded_db = st.sidebar.file_uploader("Charger un fichier .db (SQLite)", type=["db", "sqlite", "sqlite3"])
db_path_input = st.sidebar.text_input("…ou chemin vers la base", value=DEFAULT_DB_PATH)

db_path = None
if uploaded_db is not None:
    tmp_path = Path("uploaded_data.db")
    tmp_path.write_bytes(uploaded_db.getbuffer())
    db_path = str(tmp_path)
elif db_path_input and os.path.exists(db_path_input):
    db_path = db_path_input

if db_path is None:
    st.title("🏠 Dashboard DPE — Performance énergétique")
    st.warning(
        "Aucune base de données trouvée. Dépose ton fichier **.db** dans la barre latérale "
        f"ou indique un chemin valide (par défaut : `{DEFAULT_DB_PATH}`) pour afficher le dashboard."
    )
    st.stop()

try:
    batiment, consommation, qualite, emission = load_data(db_path)
except Exception as e:
    st.error(f"Impossible de lire la base de données : {e}")
    st.stop()

required_tables = {
    "batiment": batiment,
    "consommation": consommation,
    "qualite": qualite,
    "emission": emission,
}
missing_cols = []
for name, df in required_tables.items():
    if df.empty:
        missing_cols.append(name)
if missing_cols:
    st.warning(f"Tables vides ou introuvables : {', '.join(missing_cols)}. Certains graphiques peuvent manquer.")

# --- Filtres globaux ---
st.sidebar.subheader("🎛️ Filtres")

dpe_options = [d for d in ORDRE_DPE if d in batiment["etiquette_dpe"].dropna().unique()] or sorted(
    batiment["etiquette_dpe"].dropna().unique().tolist()
)
dpe_selected = st.sidebar.multiselect("Étiquette DPE", dpe_options, default=dpe_options)

type_options = sorted(batiment["type_batiment"].dropna().unique().tolist())
type_selected = st.sidebar.multiselect("Type de logement", type_options, default=type_options)

surface_min = float(batiment["surface_habitable_logement"].min())
surface_max = float(batiment["surface_habitable_logement"].max())
surface_range = st.sidebar.slider(
    "Surface habitable (m²)",
    min_value=float(surface_min),
    max_value=float(surface_max),
    value=(surface_min, surface_max),
)

st.sidebar.subheader("💶 Tarif énergie")
tarif_eur_kwh = st.sidebar.number_input(
    "Tarif (€ / kWh)", min_value=0.0, value=0.2001, step=0.01, format="%.4f"
)
tarif_eur_mwh = tarif_eur_kwh * 1000

st.sidebar.caption(f"{len(batiment):,} logements chargés au total".replace(",", " "))

# --- Application des filtres à la table bâtiment de référence ---
batiment_f = batiment[
    batiment["etiquette_dpe"].isin(dpe_selected)
    & batiment["type_batiment"].isin(type_selected)
    & batiment["surface_habitable_logement"].between(surface_range[0], surface_range[1])
]
ids_filtres = set(batiment_f["numero_dpe"])

consommation_f = consommation[consommation["numero_dpe"].isin(ids_filtres)]
qualite_f = qualite[qualite["numero_dpe"].isin(ids_filtres)] if "numero_dpe" in qualite.columns else qualite[
    qualite["etiquette_dpe"].isin(dpe_selected)
]
emission_f = emission[emission["numero_dpe"].isin(ids_filtres)] if "numero_dpe" in emission.columns else emission

if batiment_f.empty:
    st.error("Aucun logement ne correspond aux filtres sélectionnés. Élargis les filtres dans la barre latérale.")
    st.stop()

conso_bat = build_conso_bat(batiment_f, consommation_f, tarif_eur_mwh)
conso_bat_ener = build_conso_ener(batiment_f, consommation_f)

# ----------------------------------------------------------------------------
# En-tête + KPIs
# ----------------------------------------------------------------------------
st.title("🏠 Dashboard DPE — Performance énergétique des logements")
st.caption("Explore la consommation, les coûts et la qualité d'isolation des logements par étiquette DPE.")

k1, k2, k3, k4 = st.columns(4)
kpi_card(k1, "Logements (filtrés)", f"{len(batiment_f):,}".replace(",", " "))
kpi_card(
    k2,
    "Consommation moyenne",
    f"{consommation_f['consommation_annuelle_moyenne_par_site_de_ladresse_mwh'].mean():.2f} MWh",
)
kpi_card(k3, "Surface habitable moyenne", f"{batiment_f['surface_habitable_logement'].mean():.0f} m²")
kpi_card(k4, "Facture annuelle moyenne", f"{conso_bat['facture_annuelle_moyenne_euro'].mean():,.0f} €".replace(",", " "))

st.divider()

# ----------------------------------------------------------------------------
# Onglets thématiques
# ----------------------------------------------------------------------------
tab_overview, tab_conso, tab_energie, tab_histo = st.tabs(
    ["📊 Vue d'ensemble", "💶 Consommation & Prix", "⚡ Énergie", "🕰️ Historique"]
)

# --- Onglet 1 : Vue d'ensemble --------------------------------------------
with tab_overview:
    c1, c2 = st.columns(2)

    with c1:
        count_dpe = batiment_f["etiquette_dpe"].value_counts().reindex(ORDRE_DPE).dropna()
        fig1 = px.bar(
            count_dpe,
            x=count_dpe.index,
            y=count_dpe.values,
            color=count_dpe.index,
            color_discrete_map=COLORS_DPE,
            labels={"x": "Étiquette DPE", "y": "Nombre de logements"},
            title="Répartition des étiquettes DPE",
        )
        fig1.update_layout(showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)

    with c2:
        count_type = batiment_f["type_batiment"].value_counts()
        fig3 = px.bar(
            count_type,
            x=count_type.index,
            y=count_type.values,
            labels={"x": "Type de logement", "y": "Nombre de logements"},
            title="Répartition des types de logements",
        )
        st.plotly_chart(fig3, use_container_width=True)


    with c1 :
        fig_hist_1 = px.histogram(consommation_f, x= "consommation_annuelle_moyenne_par_site_de_ladresse_mwh", title="Distribution de la consomation annuelle moyenne par site")
        st.plotly_chart(fig_hist_1, use_container_width=True)

        fig_hist_3 = px.histogram(batiment_f, x= "annee_construction", title = "Distribution des annees de construction" )
        st.plotly_chart(fig_hist_3, use_container_width=True)

    with c2 :
        fig_hist_2 = px.histogram(batiment_f, x= "surface_habitable_logement", title="Distribution de la surface habitable moyenne")
        st.plotly_chart(fig_hist_2, use_container_width=True)

        fig_hist_4 = px.histogram(qualite_f, x= "deperditions_murs", title = "Distribution de la déperdition des murs" )
        st.plotly_chart(fig_hist_4, use_container_width=True)


    with st.expander("Voir les données brutes filtrées"):
        st.dataframe(batiment_f, use_container_width=True)

# --- Onglet 2 : Consommation & Prix ----------------------------------------
with tab_conso:
    consommation_type_logement = (
        conso_bat.groupby("type_batiment")
        .agg({"consommation_annuelle_moyenne_par_site_de_ladresse_mwh": "mean"})
        .reset_index()
        .sort_values(by="consommation_annuelle_moyenne_par_site_de_ladresse_mwh", ascending=False)
    )
    conso_tag = (
        conso_bat.groupby("etiquette_dpe")
        .agg({"consommation_annuelle_moyenne_par_site_de_ladresse_mwh": "mean"})
        .reset_index()
    )
    conso_tag_pondered = (
        conso_bat.groupby("etiquette_dpe").agg({"conso_ratio_surface": "mean"}).reset_index()
    )

    c1, c2 = st.columns(2)
    with c1:
        fig4 = px.bar(
            consommation_type_logement,
            x="type_batiment",
            y="consommation_annuelle_moyenne_par_site_de_ladresse_mwh",
            labels={
                "type_batiment": "Type de logement",
                "consommation_annuelle_moyenne_par_site_de_ladresse_mwh": "Consommation moyenne (MWh)",
            },
            title="Consommation moyenne par type de logement",
        )
        st.plotly_chart(fig4, use_container_width=True)

    with c2:
        fig6 = px.bar(
            conso_tag,
            x="etiquette_dpe",
            y="consommation_annuelle_moyenne_par_site_de_ladresse_mwh",
            color="etiquette_dpe",
            color_discrete_map=COLORS_DPE,
            category_orders={"etiquette_dpe": ORDRE_DPE},
            labels={
                "etiquette_dpe": "Étiquette DPE",
                "consommation_annuelle_moyenne_par_site_de_ladresse_mwh": "Consommation moyenne (MWh)",
            },
            title="Consommation moyenne par étiquette DPE",
        )
        fig6.update_layout(showlegend=False)
        st.plotly_chart(fig6, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        fig7 = px.bar(
            conso_tag_pondered,
            x="etiquette_dpe",
            y="conso_ratio_surface",
            color="etiquette_dpe",
            color_discrete_map=COLORS_DPE,
            category_orders={"etiquette_dpe": ORDRE_DPE},
            labels={"etiquette_dpe": "Étiquette DPE", "conso_ratio_surface": "Consommation / m² (MWh/m²)"},
            title="Consommation moyenne par m² selon l'étiquette DPE",
        )
        fig7.update_layout(showlegend=False)
        st.plotly_chart(fig7, use_container_width=True)

    with c4:
        fig5 = px.scatter(
            conso_bat,
            x="surface_habitable_logement",
            y="consommation_annuelle_moyenne_par_site_de_ladresse_mwh",
            color="etiquette_dpe",
            color_discrete_map=COLORS_DPE,
            category_orders={"etiquette_dpe": ORDRE_DPE},
            opacity=0.6,
            labels={
                "surface_habitable_logement": "Surface habitable (m²)",
                "consommation_annuelle_moyenne_par_site_de_ladresse_mwh": "Consommation (MWh)",
            },
            title="Consommation vs surface habitable",
        )
        st.plotly_chart(fig5, use_container_width=True)

    fig8 = px.scatter(
        conso_bat,
        x="surface_habitable_logement",
        y="facture_annuelle_par_m2",
        color="etiquette_dpe",
        color_discrete_map=COLORS_DPE,
        category_orders={"etiquette_dpe": ORDRE_DPE},
        opacity=0.7,
        labels={
            "surface_habitable_logement": "Surface habitable (m²)",
            "facture_annuelle_par_m2": "Facture annuelle par m² (€)",
        },
        title=f"Surface habitable vs facture annuelle par m² (tarif : {tarif_eur_kwh:.4f} €/kWh)",
    )
    st.plotly_chart(fig8, use_container_width=True)

# --- Onglet 3 : Énergie ------------------------------------------------------
with tab_energie:
    type_ener = batiment_f["type_energie_n1"].value_counts()

    conso_ener_group = (
        conso_bat_ener.groupby(["type_energie_n1", "type_batiment"], as_index=False)
        .agg(
            consommation_annuelle_moyenne_par_site_de_ladresse_mwh=(
                "consommation_annuelle_moyenne_par_site_de_ladresse_mwh",
                "mean",
            ),
            n=("type_batiment", "count"),
        )
        .sort_values(by="consommation_annuelle_moyenne_par_site_de_ladresse_mwh", ascending=False)
    )

    c1, c2 = st.columns(2)
    with c1:
        fig9 = px.bar(
            type_ener,
            x=type_ener.index,
            y=type_ener.values,
            labels={"x": "Type d'énergie", "y": "Nombre de logements"},
            title="Répartition des types d'énergie",
        )
        st.plotly_chart(fig9, use_container_width=True)

    with c2:
        fig10 = px.bar(
            conso_ener_group,
            x="type_energie_n1",
            y="consommation_annuelle_moyenne_par_site_de_ladresse_mwh",
            color="type_batiment",
            barmode="stack",
            labels={
                "type_energie_n1": "Type d'énergie",
                "type_batiment": "Type de bâtiment",
                "consommation_annuelle_moyenne_par_site_de_ladresse_mwh": "Consommation moyenne (MWh)",
            },
            title="Consommation moyenne par type d'énergie et de bâtiment",
        )
        st.plotly_chart(fig10, use_container_width=True)

    conso_chauffage = conso_bat_ener.groupby("etiquette_dpe").agg({"conso_chauffage_par_m2_ef": "mean"}).reindex(ORDRE_DPE).dropna()
    conso_clim = conso_bat_ener.groupby("etiquette_dpe").agg({"conso_refroidissement_par_m2_ef": "mean"}).reindex(ORDRE_DPE).dropna()
    conso_eclairage = conso_bat_ener.groupby("etiquette_dpe").agg({"conso_eclairage_par_m2_ef": "mean"}).reindex(ORDRE_DPE).dropna()

    c3, c4, c5 = st.columns(3)
    with c3:
        fig11 = px.bar(
            conso_chauffage,
            x=conso_chauffage.index,
            y="conso_chauffage_par_m2_ef",
            color=conso_chauffage.index,
            color_discrete_map=COLORS_DPE,
            labels={"x": "Étiquette DPE", "conso_chauffage_par_m2_ef": "Chauffage (kWh/m²)"},
            title="Consommation chauffage par étiquette DPE",
        )
        fig11.update_layout(showlegend=False)
        st.plotly_chart(fig11, use_container_width=True)

    with c4:
        fig12 = px.bar(
            conso_clim,
            x=conso_clim.index,
            y="conso_refroidissement_par_m2_ef",
            color=conso_clim.index,
            color_discrete_map=COLORS_DPE,
            labels={"x": "Étiquette DPE", "conso_refroidissement_par_m2_ef": "Refroidissement (kWh/m²)"},
            title="Consommation refroidissement par étiquette DPE",
        )
        fig12.update_layout(showlegend=False)
        st.plotly_chart(fig12, use_container_width=True)

    with c5:
        fig13 = px.bar(
            conso_eclairage,
            x=conso_eclairage.index,
            y="conso_eclairage_par_m2_ef",
            color=conso_eclairage.index,
            color_discrete_map=COLORS_DPE,
            labels={"x": "Étiquette DPE", "conso_eclairage_par_m2_ef": "Éclairage (kWh/m²)"},
            title="Consommation éclairage par étiquette DPE",
        )
        fig13.update_layout(showlegend=False)
        st.plotly_chart(fig13, use_container_width=True)

# --- Onglet 4 : Historique / Isolation --------------------------------------
with tab_histo:
    compte = (
        batiment_f.groupby(["etiquette_dpe", "annee_construction"]).size().reset_index(name="nb_logements")
    ).sort_values("annee_construction")

    conso_year = (
        batiment_f[["numero_dpe", "annee_construction", "surface_habitable_logement"]]
        .merge(
            consommation_f[["numero_dpe", "consommation_annuelle_moyenne_par_site_de_ladresse_mwh"]],
            on="numero_dpe",
            how="inner",
        )
        .dropna(subset=["annee_construction"])
        .sort_values("annee_construction")
    )
    conso_year["consommation_m2"] = (
        conso_year["consommation_annuelle_moyenne_par_site_de_ladresse_mwh"]
        / conso_year["surface_habitable_logement"]
    )
    conso_year_grouped = conso_year.groupby("annee_construction").agg({"consommation_m2": "mean"}).reset_index()

    fig14 = px.line(
        compte,
        x="annee_construction",
        y="nb_logements",
        color="etiquette_dpe",
        markers=True,
        color_discrete_map=COLORS_DPE,
        category_orders={"etiquette_dpe": ORDRE_DPE},
        title="Nombre de logements par année de construction et classe DPE",
        labels={"annee_construction": "Année de construction", "nb_logements": "Nombre de logements", "etiquette_dpe": "Classe DPE"},
    )
    st.plotly_chart(fig14, use_container_width=True)

    fig15 = px.line(
        conso_year_grouped,
        x="annee_construction",
        y="consommation_m2",
        labels={"annee_construction": "Année de construction", "consommation_m2": "Consommation / m² (MWh/m²)"},
        title="Consommation moyenne par m² selon l'année de construction",
    )
    st.plotly_chart(fig15, use_container_width=True)

    if "numero_dpe" in qualite_f.columns:
        qualite_join = qualite_f.copy()
    else:
        qualite_join = qualite_f

    if "qualite_isolation_murs" in qualite_join.columns:
        qualitee_tag = (
            qualite_join.groupby(["etiquette_dpe", "qualite_isolation_murs"]).size().reset_index(name="count")
        )
        fig16 = px.bar(
            qualitee_tag,
            x="etiquette_dpe",
            y="count",
            color="qualite_isolation_murs",
            barmode="stack",
            category_orders={"etiquette_dpe": ORDRE_DPE},
            title="Qualité d'isolation des murs par étiquette DPE",
            labels={"etiquette_dpe": "Étiquette DPE", "qualite_isolation_murs": "Qualité isolation murs", "count": "Nombre de logements"},
        )
        st.plotly_chart(fig16, use_container_width=True)

    deperdition_cols = [
        c
        for c in [
            "deperditions_planchers_bas",
            "deperditions_baies_vitrees",
            "deperditions_planchers_hauts",
            "deperditions_ponts_thermiques",
        ]
        if c in qualite_join.columns
    ]
    if deperdition_cols and "etiquette_dpe" in qualite_join.columns:
        deperditions_tag = qualite_join.groupby("etiquette_dpe").agg({c: "mean" for c in deperdition_cols}).reset_index()
        cols = st.columns(len(deperdition_cols))
        titres = {
            "deperditions_planchers_bas": "Planchers bas",
            "deperditions_baies_vitrees": "Baies vitrées",
            "deperditions_planchers_hauts": "Planchers hauts",
            "deperditions_ponts_thermiques": "Ponts thermiques",
        }
        for col, dcol in zip(cols, deperdition_cols):
            with col:
                fig = px.bar(
                    deperditions_tag,
                    x="etiquette_dpe",
                    y=dcol,
                    color="etiquette_dpe",
                    color_discrete_map=COLORS_DPE,
                    category_orders={"etiquette_dpe": ORDRE_DPE},
                    title=f"Déperdition — {titres.get(dcol, dcol)}",
                )
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption("Dashboard généré à partir des données DPE — filtres actifs dans la barre latérale.")