import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine

engine = create_engine("sqlite:///data/base.db")

def load(table):
    return pd.read_sql(f"SELECT * FROM {table}", con=engine)

def first_existing(df, candidates, fallback=None):
    for c in candidates:
        if c in df.columns:
            return c
    return fallback

import sqlalchemy as sa
insp = sa.inspect(engine)
silver_tables = sorted(t for t in insp.get_table_names() if t.startswith("silver_"))
print(f"{len(silver_tables)} tables silver trouvées :")
for t in silver_tables:
    print(" -", t)


df = load("silver_renta_produit")
name_col = first_existing(df, ["product_name", "name", "product_id"])

agg = df.groupby(name_col, as_index=False).agg(
    benef_product=("benef_product", "sum"),
    rentability_product=("rentability_product", "mean"),
    quantity=("quantity", "sum"),
)

fig = px.bar(
    agg.sort_values("benef_product", ascending=False),
    x=name_col, y="benef_product",
    title="Bénéfice total par produit",
    labels={name_col: "Produit", "benef_product": "Bénéfice (€)"},
    text_auto=".2s",
)
fig.show()

fig2 = px.bar(
    agg.sort_values("rentability_product", ascending=False),
    x=name_col, y="rentability_product",
    title="Rentabilité moyenne par unité vendue",
    labels={name_col: "Produit", "rentability_product": "Rentabilité (€/unité)"},
    text_auto=".2f",
    color="rentability_product",
    color_continuous_scale="RdYlGn",
)
fig2.show()


df = load("silver_top_clients")
name_col = first_existing(df, ["client_name", "name", "company_name", "client_id"])

top = df.sort_values("revenue_eur", ascending=False).head(15)

fig = px.bar(
    top, x="revenue_eur", y=name_col, orientation="h",
    title="Top 15 clients par chiffre d'affaires",
    labels={"revenue_eur": "CA (€)", name_col: "Client"},
    text_auto=".2s",
)
fig.update_layout(yaxis=dict(categoryorder="total ascending"))
fig.show()



df = load("silver_sorted_sales")
df2 = load("bronze_client")
df = df.merge(df2[["client_id", "client_name"]])
df["month"] = pd.to_datetime(df["month"])

# on limite aux 8 plus gros clients pour la lisibilité
top_ids = (
    df.groupby("client_id")["ca_cumule_client"].max()
    .sort_values(ascending=False).head(8).index
)

plot_df = df[df["client_id"].isin(top_ids)]

fig = px.line(
    plot_df, x="month", y="ca_cumule_client", color="client_name",
    title="Chiffre d'affaires cumulé par client (top 8)",
    labels={"month": "Mois", "ca_cumule_client": "CA cumulé (€)", "client_id": "Client"},
    markers=True,
)
fig.show()




df = load("silver_global_sales")


df["month"] = pd.to_datetime(df["month"])



fig = px.line(
    df, x="month", y="revenue_eur",
    title="CA global par mois — saisonnalité",
    labels={"month": "Mois", "revenue_eur": "CA (€)"},
    markers=True,
)
fig.show()

fig2 = px.bar(
    df, x="month", y="quantity",
    title="Quantités vendues par mois",
    labels={"month": "Mois", "quantity": "Quantité"},
)
fig2.show()



df_elec = load("silver_facto_prod_elec_cost")
df_usine = load("bronze_usine")

df_elec = df_elec.merge(df_usine[["factory_id", "factory_name"]], how="left", on="factory_id")

fig = px.bar(
    df_elec.sort_values("energy_consumption_kwh", ascending=False),
    x="factory_name", y="energy_consumption_kwh",
    title="Consommation d'énergie totale par usine",
    labels={"factory_name": "Usine", "energy_consumption_kwh": "Conso (kWh)"},
    text_auto=".2s",
)
fig.show()

df_conso = load("silver_conso_by_facto")
df_conso["month"] = pd.to_datetime(df_conso["month"])
df_conso = df_conso.merge(df_usine[["factory_id", "factory_name"]], how="left", on="factory_id")


fig2 = px.line(
    df_conso, x="month", y="conso_cost", color="factory_name",
    title="Coût énergétique mensuel par usine",
    labels={"month": "Mois", "conso_cost": "Coût énergie (€)", "factory_name": "Usine"},
    markers=True,
)
fig2.show()



df = load("silver_all_costs_2025")
df_all_costs = load("silver_all_costs_facto")
name_col = first_existing(df, ["factory_name", "name", "factory_id"])

fig = px.bar(
    df.sort_values("total_cost_facto", ascending=False),
    x=name_col, y="total_cost_facto",
    title="Coût total annuel par usine",
    labels={name_col: "Usine", "total_cost_facto": "Coût total (€)"},
    text_auto=".2s",
    color="country" if "country" in df.columns else None,
)
fig.show()

df_all_costs = df_all_costs.merge(df[["factory_id", "factory_name"]], how="left", on="factory_id")

# Décomposition des coûts par usine (barres empilées)
cost_cols = [c for c in ["maintenance_cost_eur", "conso_cost", "yearly_avg_cost", "rework_cost_eur"] if c in df_all_costs.columns]
melted = df_all_costs.melt(id_vars=[name_col], value_vars=cost_cols, var_name="type_cout", value_name="montant")
melted = melted.rename(columns={"maintenance_cost_eur" : "coût de maintenance", "conso_cost" : "coûts de consommation","yearly_avg_cost" : "côut moyen annuel des pièces", "rework_cost_eur" : "coûts liés à la qualité"  })

fig2 = px.bar(
    melted, x=name_col, y="montant", color="type_cout",
    title="Décomposition des coûts par usine",
    labels={name_col: "Usine", "montant": "Montant (€)", "type_cout": "Type de coût"},
)
fig2.show()


df = load("silver_all_global_cost")
df["month"] = pd.to_datetime(df["month"])

cost_cols = [c for c in ["conso_cost", "maintenance_cost_eur", "avg_global_piece_cost", "rework_cost_eur"] if c in df.columns]
melted = df.melt(id_vars=["month"], value_vars=cost_cols, var_name="type_cout", value_name="montant")

fig = px.area(
    melted, x="month", y="montant", color="type_cout",
    title="Répartition mensuelle des coûts globaux",
    labels={"month": "Mois", "montant": "Montant (€)", "type_cout": "Type de coût"},
)
fig.show()

fig2 = px.line(
    df, x="month", y="global_cost",
    title="Coût global mensuel (total)",
    labels={"month": "Mois", "global_cost": "Coût total (€)"},
    markers=True,
)
fig2.show()


df = load("silver_df_benef")
df["month"] = pd.to_datetime(df["month"])

melted1 = df.melt(id_vars=["month"], value_vars=["revenue_eur", "global_cost"],
                  var_name="indicateur", value_name="montant")

fig = px.line(
    melted1, x="month", y="montant", color="indicateur",
    title="CA et coûts mensuel",
    labels={"month": "Mois", "montant": "Montant (€)", "indicateur": "Indicateur"},
    markers=True,
)


fig.show()

fig2 = px.line(df ,x="month", y="balance", title = "Bénéfices mensuels", 
               labels={"month": "Mois", "balance": "Montant (€)"})

fig2.show()

global_benef = load("silver_global_benef")["value"].iloc[0]
fig3 = go.Figure(go.Indicator(
    mode="number",
    value=global_benef,
    number={"prefix": "€", "valueformat": ",.0f"},
    title={"text": "Bénéfice annuel global"},
))
fig3.show()



df = load("silver_benef_produit_month")
df["month"] = pd.to_datetime(df["month"])

fig = px.line(
    df, x="month", y="balance", color="product_id",
    title="Évolution mensuelle du bénéfice par produit (prix de vente - coûts)",
    labels={"month": "Mois", "balance": "Bénéfice (€)", "product_id": "Produit"},
    markers=True,
)
fig.show()


df = load("silver_machines")

fig = px.scatter(
    df, x="number_of_sensors_default", y="camera_event_id",
    text="machine_id",
    title="Alertes capteurs vs. événements caméra par machine",
    labels={"number_of_sensors_default": "Alertes capteurs (nb)", "camera_event_id": "Événements caméra (nb)"},
    size="number_of_sensors_default",
)
fig.update_traces(textposition="top center")
fig.show()



df_total = load("silver_high_severity_total")

fig = px.bar(
    df_total.sort_values("severity", ascending=False).head(15),
    x="machine_id", y="severity",
    title="Nb d'incidents HIGH par machine (total)",
    labels={"machine_id": "Machine", "severity": "Nb incidents HIGH"},
)
fig.show()

df_open = load("silver_to_resolve_count")

fig2 = px.bar(
    df_open.sort_values("resolution_time_min", ascending=False).head(15),
    x="machine_id", y="resolution_time_min",
    title="Temps de résolution cumulé — incidents HIGH non résolus",
    labels={"machine_id": "Machine", "resolution_time_min": "Temps de résolution (min)"},
    color="severity" if "severity" in df_open.columns else None,
)
fig2.show()


def load_pannes(table, label):
    d = load(table)
    d["event_timestamp"] = pd.to_datetime(d["event_timestamp"])
    d = d.rename(columns={"machine_id": "nb_pannes"})
    d["severite"] = label
    return d[["event_timestamp", "nb_pannes", "severite"]]

pannes = pd.concat([
    load_pannes("silver_nb_pannes_high", "HIGH"),
    load_pannes("silver_nb_pannes_medium", "MEDIUM"),
    load_pannes("silver_nb_pannes_low", "LOW"),
])

fig = px.line(
    pannes, x="event_timestamp", y="nb_pannes", color="severite",
    title="Nombre de pannes par mois et par sévérité",
    labels={"event_timestamp": "Mois", "nb_pannes": "Nb de pannes", "severite": "Sévérité"},
    markers=True,
)
fig.show()



df = load("silver_alerts_machines")
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["vibration_level"] = df["vibration_level"].fillna(0)
fig = px.scatter(
    df, x="timestamp", y="temperature_c", color="machine_id",
    size="vibration_level",
    title="Alertes température (taille = niveau de vibration)",
    labels={"timestamp": "Date", "temperature_c": "Température (°C)", "machine_id": "Machine"},

)
fig.show()

fig2 = px.scatter(
    df, x="timestamp", y="pressure_bar", color="machine_id",
    title="Alertes pression dans le temps",
    labels={"timestamp": "Date", "pressure_bar": "Pression (bar)", "machine_id": "Machine"},
)
fig2.show()



df = load("silver_monthly_mttr")
df2= load("bronze_usine")

df["month"] = pd.to_datetime(df["month"])
df = df.merge(df2[["factory_id", "factory_name"]], on="factory_id", how="left")
fig = px.bar(
    df, x="month", y="manque_panne", color="factory_name",
    title="Manque à gagner estimé lié aux pannes (MTTR × CA horaire moyen)",
    labels={"month": "Mois", "manque_panne": "Manque à gagner (€)", "factory_name": "Usine"},
)
fig.show()

fig2 = px.line(
    df.groupby("month", as_index=False)["mttr_hours"].sum(),
    x="month", y="mttr_hours",
    title="Total heures d'arrêt (MTTR) par mois — toutes usines",
    labels={"month": "Mois", "mttr_hours": "Heures d'arrêt"},
    markers=True,
)
fig2.show()
