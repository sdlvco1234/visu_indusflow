import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from sqlalchemy import create_engine
import sqlite3
# from pysqlcipher3 import dbapi2 as sqlite
import os
# from dotenv import load_dotenv


# load_dotenv(".env")
SOURCE_DB = "data/base.db"
ENCRYPTED_DB = "data/database_encrypted.sqlite"
# KEY = st.secrets["SECRET_KEY"]

KEY = os.environ.get("SECRET_KEY")
conn = sqlite3.connect(SOURCE_DB)

# conn = sqlite.connect(ENCRYPTED_DB)


# conn.execute(
#     f"PRAGMA key ='{KEY}'"
# )

# ----------------------------------------------------------------------------
# Configuration générale de la page
# ----------------------------------------------------------------------------

st.set_page_config(
    page_title="INDUSFLOW DASHBOARD DIRECTIONS",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        div[data-testid="stMetric"] {
            background-color: rgba(120, 120, 120, 0.08);
            border: 1px solid rgba(120, 120, 120, 0.15);
            border-radius: 12px;
            padding: 14px 18px 10px 18px;
        }
        div[data-testid="stMetricLabel"] { font-weight: 600; }
        h1, h2, h3 { padding-top: 0.2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# Authentification
# ----------------------------------------------------------------------------

with open("config.yaml") as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
)

authenticator.login(location="main")

auth_status = st.session_state.get("authentication_status")

if auth_status is False:
    st.error("Nom d'utilisateur ou mot de passe incorrect.")
    st.stop()

if auth_status is None:
    st.warning("Merci de te connecter pour accéder au dashboard.")
    st.stop()




# # À partir d'ici, l'utilisateur est authentifié.
username = st.session_state["username"]
display_name = st.session_state["name"]
user_role = config["credentials"]["usernames"][username].get("role", None)


# ----------------------------------------------------------------------------
# Rôles -> onglets autorisés
# ----------------------------------------------------------------------------
# Ajouter un rôle ici suffit à lui donner accès à un ou plusieurs onglets.
# "dg" voit tout ; les autres rôles ne voient que leur périmètre.

ROLE_PERMISSIONS = {
    "dg": ["dg", "resp_usine", "maintenance", "daf", "commercial"],
    "resp_usine": ["resp_usine"],
    "maintenance": ["maintenance"],
    "daf": ["daf"],
    "commercial": ["commercial"],
}

allowed_tabs = ROLE_PERMISSIONS.get(user_role, [])

if not allowed_tabs:
    st.error(
        f"Aucun onglet n'est associé au rôle « {user_role} ». "
        "Contacte l'administrateur du dashboard pour faire corriger ton profil."
    )
    st.stop()

# engine = create_engine("sqlite:///data/base.db")


def load(table: str) -> pd.DataFrame:
    return pd.read_sql(f"SELECT * FROM {table}", con=conn)


def safe_load(table: str):
    """Charge une table, renvoie None si elle n'existe pas encore (au lieu de faire planter tout le dashboard)."""
    try:
        return load(table)
    except Exception:
        return None


def first_existing(df, candidates, fallback=None):
    for c in candidates:
        if c in df.columns:
            return c
    return fallback


def fmt_eur(x) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x:,.0f} €".replace(",", " ")


def fmt_pct(x) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x:.1f} %"


def kpi_card(col, label, value, help_text=None):
    col.metric(label, value, help=help_text)


# ----------------------------------------------------------------------------
# Chargement des données (mis en cache)
# ----------------------------------------------------------------------------

@st.cache_data(show_spinner="Chargement des données…")
def load_data():
    data = {}

    data["renta_produit"] = load("silver_renta_produit")
    data["top_clients"] = load("silver_top_clients")
    data["sorted_sales"] = load("silver_sorted_sales")
    data["bronze_client"] = load("bronze_client")
    data["global_sales"] = load("silver_global_sales")
    data["df_elec"] = load("silver_facto_prod_elec_cost")
    data["bronze_usine"] = load("bronze_usine")
    data["df_conso"] = load("silver_conso_by_facto")
    data["all_costs_2025"] = load("silver_all_costs_2025")
    data["all_costs_facto"] = safe_load("silver_all_costs_facto")  # peut être absente, voir note dans le chat
    data["all_global_cost"] = load("silver_all_global_cost")
    data["benef"] = load("silver_df_benef")
    data["global_benef"] = load("silver_global_benef")["value"].iloc[0]
    data["benef_produit"] = load("silver_benef_produit_month")
    data["machines"] = load("silver_machines")
    data["high_severity_total"] = load("silver_high_severity_total")
    data["to_resolve"] = load("silver_to_resolve_count")
    data["alertes_machines"] = load("silver_alerts_machines")
    data["monthly_mttr"] = load("silver_monthly_mttr")
    data["produit"] = load("bronze_produit")
    data["ventes"] = load("bronze_ventes")

    # Conversions de dates faites une seule fois, ici
    for key in ["global_sales", "sorted_sales", "df_conso", "all_global_cost", "benef", "benef_produit", "monthly_mttr"]:
        if "month" in data[key].columns:
            data[key]["month"] = pd.to_datetime(data[key]["month"])

    data["alertes_machines"]["timestamp"] = pd.to_datetime(data["alertes_machines"]["timestamp"])
    data["alertes_machines"]["vibration_level"] = data["alertes_machines"]["vibration_level"].fillna(0)

    def load_pannes(table, label):
        d = load(table)
        d["event_timestamp"] = pd.to_datetime(d["event_timestamp"])
        d = d.rename(columns={"machine_id": "nb_pannes"})
        d["severite"] = label
        return d[["event_timestamp", "nb_pannes", "severite"]]

    data["pannes"] = pd.concat([
        load_pannes("silver_nb_pannes_high", "HIGH"),
        load_pannes("silver_nb_pannes_medium", "MEDIUM"),
        load_pannes("silver_nb_pannes_low", "LOW"),
    ])

    return data


# # ============================================================================
# # FONCTIONS DE RENDU — une par onglet
# # ============================================================================

def render_dg(data):
    st.header("Vue d'ensemble")

    benef = data["benef"]
    global_benef = data["global_benef"]
    ca_totale = benef["revenue_eur"].sum()
    cout_total = benef["global_cost"].sum()
    marge_pct = (global_benef / ca_totale * 100) if ca_totale else None

    c1, c2, c3, c4 = st.columns(4)
    kpi_card(c1, "Bénéfice annuel", fmt_eur(global_benef))
    kpi_card(c2, "Chiffre d'affaires annuel", fmt_eur(ca_totale))
    kpi_card(c3, "Coûts totaux annuels", fmt_eur(cout_total))
    kpi_card(c4, "Marge nette", fmt_pct(marge_pct))

    st.divider()

    col_left, col_right = st.columns([2, 1])

    with col_left:
        melted1 = benef.melt(
            id_vars=["month"], value_vars=["revenue_eur", "global_cost"],
            var_name="indicateur", value_name="montant",
        ).replace({"revenue_eur": "Chiffre d'affaires", "global_cost": "Coûts"})

        fig = px.line(
            melted1, x="month", y="montant", color="indicateur",
            title="CA et coûts mensuels",
            labels={"month": "Mois", "montant": "Montant (€)", "indicateur": "Indicateur"},
            markers=True,
        )
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.line(
            benef, x="month", y="balance", title="Bénéfice mensuel",
            labels={"month": "Mois", "balance": "Montant (€)"}, markers=True,
        )
        fig2.update_traces(line_color="#2ca02c")
        st.plotly_chart(fig2, use_container_width=True)

    with col_right:
        st.subheader("Top 5 produits")
        renta = data["renta_produit"]
        name_col = first_existing(renta, ["product_name", "name", "product_id"])
        top5_produits = (
            renta.groupby(name_col, as_index=False)["benef_product"].sum()
            .sort_values("benef_product", ascending=False).head(5)
        )
        fig3 = px.bar(
            top5_produits, x="benef_product", y=name_col, orientation="h",
            labels={"benef_product": "Bénéfice (€)", name_col: ""}, text_auto=".2s",
        )
        fig3.update_layout(yaxis=dict(categoryorder="total ascending"), showlegend=False, height=250)
        st.plotly_chart(fig3, use_container_width=True)

        st.subheader("Top 5 clients")
        top_clients = data["top_clients"]
        cname_col = first_existing(top_clients, ["client_name", "name", "company_name", "client_id"])
        top5_clients = top_clients.sort_values("revenue_eur", ascending=False).head(5)
        fig4 = px.bar(
            top5_clients, x="revenue_eur", y=cname_col, orientation="h",
            labels={"revenue_eur": "CA (€)", cname_col: ""}, text_auto=".2s",
        )
        fig4.update_layout(yaxis=dict(categoryorder="total ascending"), showlegend=False, height=250)
        st.plotly_chart(fig4, use_container_width=True)


def render_usines(data):
    st.header("Performance des usines")

    df_usine = data["bronze_usine"]
    usines_dispo = sorted(df_usine["factory_name"].dropna().unique()) if "factory_name" in df_usine.columns else sorted(df_usine["factory_id"].unique())
    usines_selectionnees = st.multiselect(
        "Filtrer par usine (laisser vide pour tout afficher)", options=usines_dispo, default=[],
    )

    def filtre_usine(df, col="factory_name"):
        if usines_selectionnees and col in df.columns:
            return df[df[col].isin(usines_selectionnees)]
        return df

    tab_energie, tab_couts, tab_machines = st.tabs(["⚡ Énergie", "💰 Coûts", "🖥️ Machines"])

    with tab_energie:
        df_elec = data["df_elec"].merge(df_usine[["factory_id", "factory_name"]], how="left", on="factory_id") \
            if "factory_name" in df_usine.columns else data["df_elec"]
        name_col_elec = "factory_name" if "factory_name" in df_elec.columns else "factory_id"

        fig = px.bar(
            filtre_usine(df_elec, name_col_elec).sort_values("energy_consumption_kwh", ascending=False),
            x=name_col_elec, y="energy_consumption_kwh",
            title="Consommation d'énergie totale par usine",
            labels={name_col_elec: "Usine", "energy_consumption_kwh": "Conso (kWh)"},
            text_auto=".2s",
        )
        st.plotly_chart(fig, use_container_width=True)

        df_conso = data["df_conso"].merge(df_usine[["factory_id", "factory_name"]], how="left", on="factory_id") \
            if "factory_name" in df_usine.columns else data["df_conso"]
        name_col_conso = "factory_name" if "factory_name" in df_conso.columns else "factory_id"

        fig2 = px.line(
            filtre_usine(df_conso, name_col_conso), x="month", y="conso_cost", color=name_col_conso,
            title="Coût énergétique mensuel par usine",
            labels={"month": "Mois", "conso_cost": "Coût énergie (€)", name_col_conso: "Usine"},
            markers=True,
        )
        st.plotly_chart(fig2, use_container_width=True)

    with tab_couts:
        df_costs = data["all_costs_2025"]
        name_col_costs = first_existing(df_costs, ["factory_name", "name", "factory_id"])

        fig = px.bar(
            filtre_usine(df_costs, name_col_costs).sort_values("total_cost_facto", ascending=False),
            x=name_col_costs, y="total_cost_facto",
            title="Coût total annuel par usine",
            labels={name_col_costs: "Usine", "total_cost_facto": "Coût total (€)"},
            text_auto=".2s",
            color="country" if "country" in df_costs.columns else None,
        )
        st.plotly_chart(fig, use_container_width=True)

        df_all_costs_facto = data["all_costs_facto"]
        if df_all_costs_facto is None:
            st.warning(
                "La table `silver_all_costs_facto` n'existe pas encore dans la base. "
                "Ajoute-la à ton ETL pour afficher la décomposition des coûts par usine."
            )
        else:
            df_all_costs_facto = df_all_costs_facto.merge(
                df_costs[[c for c in ["factory_id", "factory_name"] if c in df_costs.columns]],
                how="left", on="factory_id",
            )
            name_col_decomp = "factory_name" if "factory_name" in df_all_costs_facto.columns else "factory_id"

            cost_cols = [c for c in ["maintenance_cost_eur", "conso_cost", "yearly_avg_cost", "rework_cost_eur"] if c in df_all_costs_facto.columns]
            melted = df_all_costs_facto.melt(id_vars=[name_col_decomp], value_vars=cost_cols, var_name="type_cout", value_name="montant")
            melted["type_cout"] = melted["type_cout"].replace({
                "maintenance_cost_eur": "Coût de maintenance",
                "conso_cost": "Coûts de consommation",
                "yearly_avg_cost": "Coût moyen annuel des pièces",
                "rework_cost_eur": "Coûts liés à la qualité",
            })

            fig2 = px.bar(
                filtre_usine(melted, name_col_decomp), x=name_col_decomp, y="montant", color="type_cout",
                title="Décomposition des coûts par usine",
                labels={name_col_decomp: "Usine", "montant": "Montant (€)", "type_cout": "Type de coût"},
            )
            st.plotly_chart(fig2, use_container_width=True)

    with tab_machines:
        df_machines = data["machines"]
        fig = px.scatter(
            df_machines, x="number_of_sensors_default", y="camera_event_id",
            text="machine_id",
            title="Alertes capteurs vs. événements caméra par machine",
            labels={"number_of_sensors_default": "Alertes capteurs (nb)", "camera_event_id": "Événements caméra (nb)"},
            size="number_of_sensors_default",
        )
        fig.update_traces(textposition="top center")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Chaque point représente une machine sous surveillance capteurs/caméra.")


def render_maintenance(data):
    st.header("Maintenance & fiabilité")

    monthly_mttr = data["monthly_mttr"]
    c1, c2, c3 = st.columns(3)
    kpi_card(c1, "Manque à gagner total lié aux pannes", fmt_eur(monthly_mttr["manque_panne"].sum()))
    kpi_card(c2, "Heures d'arrêt cumulées (MTTR)", f"{monthly_mttr['mttr_hours'].sum():,.0f} h".replace(",", " "))
    kpi_card(c3, "Incidents HIGH non résolus", f"{int(data['to_resolve']['severity'].sum()) if 'severity' in data['to_resolve'].columns else len(data['to_resolve'])}")

    st.divider()

    tab_incidents, tab_pannes, tab_capteurs, tab_cout_pannes = st.tabs(
        ["🚨 Incidents", "📉 Pannes dans le temps", "🌡️ Alertes capteurs", "💸 Coût des pannes"]
    )

    with tab_incidents:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                data["high_severity_total"].sort_values("severity", ascending=False).head(15),
                x="machine_id", y="severity",
                title="Nb d'incidents HIGH par machine (total)",
                labels={"machine_id": "Machine", "severity": "Nb incidents HIGH"},
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            df_open = data["to_resolve"]
            fig2 = px.bar(
                df_open.sort_values("resolution_time_min", ascending=False).head(15),
                x="machine_id", y="resolution_time_min",
                title="Temps de résolution cumulé — incidents HIGH non résolus",
                labels={"machine_id": "Machine", "resolution_time_min": "Temps de résolution (min)"},
                color="severity" if "severity" in df_open.columns else None,
            )
            st.plotly_chart(fig2, use_container_width=True)

    with tab_pannes:
        fig = px.line(
            data["pannes"], x="event_timestamp", y="nb_pannes", color="severite",
            title="Nombre de pannes par mois et par sévérité",
            labels={"event_timestamp": "Mois", "nb_pannes": "Nb de pannes", "severite": "Sévérité"},
            markers=True,
            color_discrete_map={"HIGH": "#d62728", "MEDIUM": "#ff7f0e", "LOW": "#2ca02c"},
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab_capteurs:
        df_alertes = data["alertes_machines"]
        col1, col2 = st.columns(2)
        with col1:
            fig = px.scatter(
                df_alertes, x="timestamp", y="temperature_c", color="machine_id",
                size="vibration_level",
                title="Alertes température (taille = niveau de vibration)",
                labels={"timestamp": "Date", "temperature_c": "Température (°C)", "machine_id": "Machine"},
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig2 = px.scatter(
                df_alertes, x="timestamp", y="pressure_bar", color="machine_id",
                title="Alertes pression dans le temps",
                labels={"timestamp": "Date", "pressure_bar": "Pression (bar)", "machine_id": "Machine"},
            )
            st.plotly_chart(fig2, use_container_width=True)

    with tab_cout_pannes:
        df_usine = data["bronze_usine"]
        df_mttr = monthly_mttr.merge(
            df_usine[[c for c in ["factory_id", "factory_name"] if c in df_usine.columns]],
            on="factory_id", how="left",
        )
        name_col_mttr = "factory_name" if "factory_name" in df_mttr.columns else "factory_id"

        fig = px.bar(
            df_mttr, x="month", y="manque_panne", color=name_col_mttr,
            title="Manque à gagner estimé lié aux pannes (MTTR × CA horaire moyen)",
            labels={"month": "Mois", "manque_panne": "Manque à gagner (€)", name_col_mttr: "Usine"},
        )
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.line(
            df_mttr.groupby("month", as_index=False)["mttr_hours"].sum(),
            x="month", y="mttr_hours",
            title="Total heures d'arrêt (MTTR) par mois — toutes usines",
            labels={"month": "Mois", "mttr_hours": "Heures d'arrêt"},
            markers=True,
        )
        st.plotly_chart(fig2, use_container_width=True)


def render_daf(data):

    st.header("Pilotage financier")

    # global_benef = data["global_benef"]

    benef = data["benef"]
    global_benef = data["global_benef"]
    ca_totale = benef["revenue_eur"].sum()
    cout_total = benef["global_cost"].sum()
    marge_pct = (global_benef / ca_totale * 100) if ca_totale else None

    c1, c2, c3, c4 = st.columns(4)
    kpi_card(c1, "Bénéfice annuel", fmt_eur(global_benef))
    kpi_card(c2, "Chiffre d'affaires annuel", fmt_eur(ca_totale))
    kpi_card(c3, "Coûts totaux annuels", fmt_eur(cout_total))
    kpi_card(c4, "Marge nette", fmt_pct(marge_pct))

    st.divider()

    tab_rentabilite, tab_couts_globaux, tab_produit = st.tabs(
        ["📈 Rentabilité produit", "🧾 Coûts globaux", "🧮 Bénéfice par produit"]
    )

    with tab_rentabilite:
        renta = data["renta_produit"]
        name_col = first_existing(renta, ["product_name", "name", "product_id"])
        agg = renta.groupby(name_col, as_index=False).agg(
            benef_product=("benef_product", "sum"),
            rentability_product=("rentability_product", "mean"),
            quantity=("quantity", "sum"),
        )

        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                agg.sort_values("benef_product", ascending=False),
                x=name_col, y="benef_product",
                title="Bénéfice total par produit",
                labels={name_col: "Produit", "benef_product": "Bénéfice (€)"},
                text_auto=".2s",
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig2 = px.bar(
                agg.sort_values("rentability_product", ascending=False),
                x=name_col, y="rentability_product",
                title="Rentabilité moyenne par unité vendue",
                labels={name_col: "Produit", "rentability_product": "Rentabilité (€/unité)"},
                text_auto=".2f",
                color="rentability_product",
                color_continuous_scale="RdYlGn",
            )
            st.plotly_chart(fig2, use_container_width=True)

    with tab_couts_globaux:
        df_global_cost = data["all_global_cost"]
        cost_cols = [c for c in ["conso_cost", "maintenance_cost_eur", "avg_global_piece_cost", "rework_cost_eur"] if c in df_global_cost.columns]
        melted = df_global_cost.melt(id_vars=["month"], value_vars=cost_cols, var_name="type_cout", value_name="montant")
        melted["type_cout"] = melted["type_cout"].replace({
            "conso_cost": "Énergie",
            "maintenance_cost_eur": "Maintenance",
            "avg_global_piece_cost": "Pièces détachées",
            "rework_cost_eur": "Qualité",
        })

        fig = px.area(
            melted, x="month", y="montant", color="type_cout",
            title="Répartition mensuelle des coûts globaux",
            labels={"month": "Mois", "montant": "Montant (€)", "type_cout": "Type de coût"},
        )
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.line(
            df_global_cost, x="month", y="global_cost",
            title="Coût global mensuel (total)",
            labels={"month": "Mois", "global_cost": "Coût total (€)"},
            markers=True,
        )
        st.plotly_chart(fig2, use_container_width=True)

    with tab_produit:
        benef_produit = data["benef_produit"]
        produit = data["produit"]

        benef_produit = benef_produit.merge(produit[['product_id', 'product_name']], on='product_id', how= "left")

        fig = px.line(
            benef_produit, x="month", y="balance", color="product_name",
            title="Évolution mensuelle du bénéfice par produit (prix de vente - coûts)",
            labels={"month": "Mois", "balance": "Bénéfice (€)", "product_id": "Produit"},
            markers=True,
        )
        st.plotly_chart(fig, use_container_width=True)
   

def render_commercial(data):

    st.header("Performance commerciale")

    top_clients = data["top_clients"]
    global_sales = data["global_sales"]

    c1, c2, c3 = st.columns(3)
    kpi_card(c1, "CA annuel total", fmt_eur(global_sales["revenue_eur"].sum()))
    kpi_card(c2, "Quantités vendues", f"{global_sales['quantity'].sum():,.0f}".replace(",", " "))
    kpi_card(c3, "Nombre de clients actifs", f"{top_clients['client_id'].nunique() if 'client_id' in top_clients.columns else len(top_clients)}")

    st.divider()

    tab_clients, tab_prod, tab_saisonnalite = st.tabs(["🤝 Clients", "🧮 Produits", "📅 Saisonnalité"])

    with tab_clients:
        cname_col = first_existing(top_clients, ["client_name", "name", "company_name", "client_id"])
        top = top_clients.sort_values("revenue_eur", ascending=False).head(15)

        fig = px.bar(
            top, x="revenue_eur", y=cname_col, orientation="h",
            title="Top 15 clients par chiffre d'affaires",
            labels={"revenue_eur": "CA (€)", cname_col: "Client"},
            text_auto=".2s",
        )
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fig, use_container_width=True)

        sorted_sales = data["sorted_sales"].merge(data["bronze_client"][["client_id", "client_name"]], how="left")
        top_ids = (
            sorted_sales.groupby("client_id")["ca_cumule_client"].max()
            .sort_values(ascending=False).head(8).index
        )
        plot_df = sorted_sales[sorted_sales["client_id"].isin(top_ids)]

        fig2 = px.line(
            plot_df, x="month", y="ca_cumule_client", color="client_name",
            title="Chiffre d'affaires cumulé par client (top 8)",
            labels={"month": "Mois", "ca_cumule_client": "CA cumulé (€)", "client_name": "Client"},
            markers=True,
        )
        st.plotly_chart(fig2, use_container_width=True)


        benef_produit = data["benef_produit"]
        produit = data["produit"]
        
        benef_produit = benef_produit.merge(produit[['product_id', 'product_name']], on='product_id', how= "left")
            
    with tab_prod:

        fig3 = px.line(
                    benef_produit, x="month", y="balance", color="product_name",
                    title="Évolution mensuelle du bénéfice par produit (prix de vente - coûts)",
                    labels={"month": "Mois", "balance": "Bénéfice (€)", "product_id": "Produit"},
                    markers=True,
                )
        st.plotly_chart(fig3, use_container_width=True, key="benefice_produits_chart")

        c1, c2= st.columns(2)

        with c1 :

            st.subheader("Top 10 produits par rentabilité")

            renta = data["renta_produit"]
            name_col = first_existing(renta, ["product_name", "name", "product_id"])
            top5_produits = (
                renta.groupby(name_col, as_index=False)["benef_product"].sum()
                .sort_values("benef_product", ascending=False).head(10)
            )
            fig3 = px.bar(
                top5_produits, x="benef_product", y=name_col, orientation="h",
                labels={"benef_product": "Bénéfice (€)", name_col: ""}, text_auto=".2s",
            )
            fig3.update_layout(yaxis=dict(categoryorder="total ascending"), showlegend=False, height=250)
            st.plotly_chart(fig3, use_container_width=True, key ="top10_renta_produit")

        with c2 :

            st.subheader("Top 10 produits par volume")
    
            ventes = data["ventes"]
            produit = data["produit"]
            volume = ventes.merge(produit, on="product_id", how ="left").groupby("product_name").agg({"quantity" : sum}).reset_index().sort_values("quantity", ascending = False).head(10)
    
            # cname_col = first_existing(top_clients, ["client_name", "name", "company_name", "client_id"])
            # top5_clients = top_clients.sort_values("revenue_eur", ascending=False).head(10)
            fig4 = px.bar(
                volume, x="quantity", y="product_name", orientation="h",
                labels={"product_name": "product"}, text_auto=".2s",
            )
            fig4.update_layout(yaxis=dict(categoryorder="total ascending"), showlegend=False, height=250)
            st.plotly_chart(fig4, use_container_width=True, key= "top10_produits_volume")


    with tab_saisonnalite:
       
        fig = px.line(
            global_sales, x="month", y="revenue_eur",
            title="CA global par mois — saisonnalité",
            labels={"month": "Mois", "revenue_eur": "CA (€)"},
            markers=True,
        )
        st.plotly_chart(fig, use_container_width=True)

        fig2 = px.bar(
            global_sales, x="month", y="quantity",
            title="Quantités vendues par mois",
            labels={"month": "Mois", "quantity": "Quantité"},
        )
        st.plotly_chart(fig2, use_container_width=True)
    


# # ============================================================================
# # Table de correspondance clé de rôle -> (libellé de l'onglet, fonction de rendu)
# # ============================================================================

TABS_CONFIG = {
    "dg": ("📊 Direction Générale", render_dg),
    "resp_usine": ("🏭 Direction d'usines", render_usines),
    "maintenance": ("🔧 Direction de Maintenance", render_maintenance),
    "daf": ("💶 Direction Financière", render_daf),
    "commercial": ("🤝 Direction Commerciale", render_commercial),
}

# # ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------

st.sidebar.title("🏭 INDUSFLOW")
st.sidebar.caption("Dashboard de pilotage — Analyse de la performance des usines")
st.sidebar.divider()
st.sidebar.write(f"👤 **{display_name}**")
st.sidebar.caption(f"Rôle : `{user_role}`")
authenticator.logout("🚪 Se déconnecter", location="sidebar")

if st.sidebar.button("🔄 Rafraîchir les données"):
    st.cache_data.clear()
    st.rerun()

# # ----------------------------------------------------------------------------
# # Chargement des données et rendu
# # ----------------------------------------------------------------------------

try:
    data = load_data()
except Exception as e:
    st.error(f"Impossible de lire la base de données : {e}")
    st.stop()

st.title("🏭 INDUSFLOW DASHBOARD DIRECTIONS")
st.caption("Analyse de la performance des usines")

tab_labels = [TABS_CONFIG[key][0] for key in allowed_tabs]
tabs = st.tabs(tab_labels)

for tab, key in zip(tabs, allowed_tabs):
    with tab:
        TABS_CONFIG[key][1](data)

st.divider()
st.caption("Dashboard créé à partir des données Indusflow")