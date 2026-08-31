import pandas as pd 
import plotly.express as px
from sqlalchemy import create_engine
from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from pysqlcipher3 import dbapi2 as sqlite

import ipywidgets as widgets
from IPython.display import display, clear_output
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import create_engine, inspect


# Imports : 


usines = pd.read_csv("data/bloc5_usines.csv")
production = pd.read_csv("data/bloc5_production_mensuelle.csv")
prix_ener = pd.read_csv("data/bloc5_prix_energie_marche.csv")
stock_pieces= pd.read_csv("data/bloc5_stock_pieces_detachees.csv")
qualitee = pd.read_csv("data/bloc5_qualite_mensuelle.csv")
maintenance = pd.read_csv("data/bloc5_maintenance_mensuelle.csv")
benchmark = pd.read_csv("data/bloc5_benchmark_industriel_externe.csv")
ventes = pd.read_csv("data/bloc5_ventes_contrats.csv")
produit = pd.read_csv("data/bloc5_produits.csv")
client = pd.read_csv("data/bloc5_clients_industriels.csv")

camera = pd.read_csv("data/machines/cameras_qualite.csv")
capteurs = pd.read_csv("data/machines/capteurs_machines.csv")
logs = pd.read_csv("data/machines/logs_erreurs_machines.csv")

# Modification des types 
usines["factory_id"] = usines["factory_id"].astype(str)
production["factory_id"] = production["factory_id"].astype(str)
stock_pieces["factory_id"] = stock_pieces["factory_id"].astype(str)
stock_pieces["part_id"] = stock_pieces["part_id"].astype(str)
qualitee["factory_id"] = qualitee["factory_id"].astype(str)
maintenance["factory_id"] = maintenance["factory_id"].astype(str)
ventes["client_id"] = ventes["client_id"].astype(str)
ventes["product_id"] = ventes["product_id"].astype(str)
produit["product_id"] = produit["product_id"].astype(str)
client["client_id"] = client["client_id"].astype(str)


production["month"] = pd.to_datetime(production["month"])
prix_ener["month"] = pd.to_datetime(prix_ener["month"])
qualitee["month"] = pd.to_datetime(qualitee["month"])
maintenance["month"]=pd.to_datetime(maintenance["month"])
ventes["month"]=pd.to_datetime(ventes["month"])

capteurs["timestamp"] = pd.to_datetime(capteurs["timestamp"])


# Feature Engineering


production["target_rate"] = production["production_cycles"] / production["target_cycles"]
production["energy_per_cycle_kwh"] = production["energy_consumption_kwh"] / production["production_cycles"]

maintenance["total_maintenance_count"] = (
        maintenance["preventive_maintenance_count"]
        + maintenance["corrective_maintenance_count"]
    )

maintenance["pre"] = maintenance["preventive_maintenance_count"] /maintenance["total_maintenance_count"]

maintenance["maintenance_cost_per_intervention"] =  maintenance["maintenance_cost_eur"] / maintenance["total_maintenance_count"]

maintenance["corrective_cost"] = maintenance["corrective_maintenance_count"] * maintenance["maintenance_cost_per_intervention"]


# Import base bronze 

load_dotenv(".env")



ENCRYPTED_DB = "data/database_encrypted.sqlite"

KEY = os.environ.get("SECRET_KEY")

def get_db_connection():
    conn = sqlite.connect(ENCRYPTED_DB)

    conn.execute(
        f"PRAGMA key ='{KEY}'"
    )

    return conn

conn = get_db_connection()

# engine = create_engine(
#     "sqlite://",
#     creator=get_connection,
#     poolclass=StaticPool,
# )

usines.to_sql("bronze_usine", con=conn, if_exists="append",index=False)
production.to_sql("bronze_production", con=conn, if_exists="append",index=False)
prix_ener.to_sql("bronze_prix_ener", con=conn, if_exists="append",index=False)
stock_pieces.to_sql("bronze_stock_pieces", con=conn, if_exists="append",index=False)
qualitee.to_sql("bronze_qualitee", con=conn, if_exists="append",index=False)
maintenance.to_sql("bronze_maintenance", con=conn, if_exists="append",index=False)
benchmark.to_sql("bronze_benchmark", con=conn, if_exists="append",index=False)
ventes.to_sql("bronze_ventes", con=conn, if_exists="append",index=False)
produit.to_sql("bronze_produit", con=conn, if_exists="append",index=False)
client.to_sql("bronze_client", con=conn, if_exists="append",index=False)
camera.to_sql("bronze_camera", con=conn, if_exists="append",index=False)
capteurs.to_sql("bronze_capteurs", con=conn, if_exists="append",index=False)
logs.to_sql("bronze_logs", con=conn, if_exists="append",index=False)

# Transformation 
## CA & rentabilité

renta_produit = ventes[["month", "product_id", "quantity", "revenue_eur"]].merge(produit, on = "product_id", how="inner")

renta_produit["cost_eur"] = renta_produit["quantity"] * renta_produit["unit_cost_eur"] # coûts totaux par produit 
renta_produit["benef_product"] = renta_produit["revenue_eur"] - renta_produit["cost_eur"]  
renta_produit["benef_product"] = renta_produit["benef_product"].round(2) # bénéfice total par produit
renta_produit["rentability_product"] = renta_produit["benef_product"] / renta_produit["quantity"] # bénéfice rapporté par produit

# renta_produit_year = renta_produit.groupby("product_id").sum().reset_index()


# top clients

top_clients = ventes.groupby("client_id").agg({"quantity" : "sum", "revenue_eur": "sum"}).sort_values("revenue_eur", ascending=False)
top_clients = client.merge(top_clients, on="client_id", how="left")


sorted_sales = ventes.sort_values(["client_id", "month"])
sorted_sales["ca_cumule_client"] = sorted_sales.groupby("client_id")["revenue_eur"].cumsum()
sorted_sales["quantitee_cumule_client"] = sorted_sales.groupby("client_id")["quantity"].cumsum()


# Saisonalité ventes globales

global_sales = ventes.groupby("month").agg({"quantity": sum, "revenue_eur" : sum}).reset_index()

facto_maintenance_costs = maintenance.groupby("factory_id").agg({"maintenance_cost_eur" : sum, "mttr_hours" : sum, "mtbf_hours" :sum}) # cout de maintenance par usine sur l'année
global_maintenance_costs = maintenance.groupby("month").agg({"maintenance_cost_eur" : sum, "mttr_hours" : sum, "mtbf_hours" :sum})

facto_prod_elec_cost = production.groupby("factory_id").agg({"energy_consumption_kwh" :sum}).reset_index()
conso_by_facto = production[["month","factory_id", "energy_consumption_kwh"]].merge(usines[["factory_id", "country", "machine_count"]], on="factory_id", how="left")


## Coûts énergétiques
conso_by_facto["code_price"] = conso_by_facto["month"].astype(str) + "_" + conso_by_facto["country"].astype(str)
prix_ener["code_price"] = prix_ener["month"].astype(str) + "_" + prix_ener["country"].astype(str)

conso_by_facto =conso_by_facto.merge(prix_ener[["code_price", "energy_price_eur_kwh"]], on="code_price", how="left")
conso_by_facto["conso_cost"] = conso_by_facto["energy_consumption_kwh"] * conso_by_facto["energy_price_eur_kwh"]
cost_ener_per_facto = conso_by_facto.groupby("factory_id").agg({"conso_cost" : sum,"country" :"first", "machine_count" :"first"})

global_ener_cost = conso_by_facto.groupby("month").agg({"conso_cost" : sum})

## Couts qualité 

facto_qualitee_cost= qualitee.groupby("factory_id").agg({"rework_cost_eur" :sum})
global_qualitee_cost = qualitee.groupby("month").agg({"rework_cost_eur" : sum})

## Coûts pièces 


stock_pieces["yearly_avg_usage"] = stock_pieces["avg_monthly_usage"] * 12
stock_pieces["yearly_avg_cost"] = stock_pieces["yearly_avg_usage"] * stock_pieces["unit_price_eur"]
stock_pieces["monthly_avg_cost"] = stock_pieces["avg_monthly_usage"] * stock_pieces["unit_price_eur"]

facto_stock_costs = stock_pieces.groupby("factory_id").agg({"avg_monthly_usage" : sum, "yearly_avg_cost" : sum})
facto_stock_costs = facto_stock_costs.rename(columns={"avg_monthly_usage" : "avg_pieces_usage"})

avg_global_piece_cost = float(stock_pieces.groupby("part_id").agg({"monthly_avg_cost" : sum}).sum().iloc[0])


# Coûts totaux par usines

df_costs_list = [facto_maintenance_costs, cost_ener_per_facto, facto_stock_costs,facto_qualitee_cost]

all_costs = pd.concat(df_costs_list, axis=1).reset_index()
all_costs ["total_cost_facto"] = all_costs["maintenance_cost_eur"] + all_costs["conso_cost"] + all_costs["yearly_avg_cost"] + all_costs["rework_cost_eur"]

all_costs_2025 = all_costs[["factory_id", "total_cost_facto"]].merge(usines)

df_costs_list = [facto_maintenance_costs, cost_ener_per_facto, facto_stock_costs,facto_qualitee_cost]
all_costs_facto = pd.concat(df_costs_list, axis=1).reset_index()

# # Coûts totaux par usines

df_costs_list = [facto_maintenance_costs, cost_ener_per_facto, facto_stock_costs,facto_qualitee_cost]

all_costs = pd.concat(df_costs_list, axis=1).reset_index()
all_costs ["total_cost_facto"] = all_costs["maintenance_cost_eur"] + all_costs["conso_cost"] + all_costs["yearly_avg_cost"] + all_costs["rework_cost_eur"]

all_costs_2025 = all_costs[["factory_id", "total_cost_facto"]].merge(usines)

# Coûts mensuels globaux

df_global_cost_list = [global_qualitee_cost,global_ener_cost, global_maintenance_costs]
all_global_cost = pd.concat(df_global_cost_list, axis=1).reset_index()
all_global_cost["avg_global_piece_cost"] = avg_global_piece_cost
all_global_cost["global_cost"] = all_global_cost["conso_cost"] + all_global_cost["maintenance_cost_eur"] + all_global_cost["avg_global_piece_cost"] + all_global_cost["rework_cost_eur"]

## Bénéfices
#Bénéfices mensuels

df_ca = ventes.groupby("month").agg({"revenue_eur": sum}).reset_index()
df_benef = all_global_cost[["month", "global_cost"]].merge(df_ca) 
df_benef["balance"] = df_benef["revenue_eur"] - df_benef["global_cost"]

#Bénéfice annuel

global_benef = float(df_benef["balance"].sum())

#Bénéfice de chaque produit

products_sales = ventes[["month", "product_id", "quantity", "revenue_eur"]].merge(produit[["product_id", "unit_cost_eur" ]], on = "product_id", how="left")
products_sales["balance"] = products_sales["revenue_eur"] - (products_sales["quantity"] * products_sales["unit_cost_eur"])
benef_produit_month = products_sales.groupby(["month","product_id"]).sum().reset_index()[["month", "product_id","balance"]]

#Maintenance 

camera = camera[camera["confidence_score"] > 0.90]
capteurs = capteurs[
    (capteurs["temperature_c"] >= 100)|(capteurs["temperature_c"] <= 10) | (capteurs["vibration_level"] >= 80) | (capteurs["pressure_bar"] >= 13)
]

machine_w_sensors = capteurs.groupby("machine_id").agg({"sensor_id" : "count"}).reset_index()
machine_w_camera = camera.groupby("machine_id").agg({"camera_event_id" : "count"}).reset_index()

machines = machine_w_sensors.merge(machine_w_camera, how="left").rename(columns={"sensor_id": "number_of_sensors_default"})


# Nombre d'incidents par machine à résoudre : 

high_severity_total = logs[logs["severity"] == "HIGH"]
high_severity_total = high_severity_total.groupby("machine_id").agg({"severity" : "count", "resolution_time_min": sum}).reset_index()


high_severity = logs[logs["severity"] == "HIGH"]
to_resolve = high_severity[high_severity["resolved"]==0]

to_resolve_count = to_resolve.groupby("machine_id").agg({"severity" : "count", "resolution_time_min": sum}).reset_index()

# Nombre de pannes dans le temps 

logs["event_timestamp"] = pd.to_datetime(logs["event_timestamp"] )

nb_pannes_global= logs[["event_timestamp", "machine_id"]].set_index("event_timestamp").resample("ME").count()

high_severity = logs[logs["severity"] == "HIGH"]
medium_severity = logs[logs["severity"] == "MEDIUM"]
low_severity = logs[logs["severity"] == "LOW"]


nb_pannes_high = high_severity[["event_timestamp", "machine_id"]].set_index("event_timestamp").resample("ME").count().reset_index()
nb_pannes_medium = medium_severity[["event_timestamp", "machine_id"]].set_index("event_timestamp").resample("ME").count().reset_index()
nb_pannes_low = low_severity[["event_timestamp", "machine_id"]].set_index("event_timestamp").resample("ME").count().reset_index()


## Cause des pannes 

alerts_machines = capteurs[["timestamp", "machine_id", "temperature_c", "vibration_level", "pressure_bar" ]].set_index("timestamp").sort_values("machine_id").reset_index()
date_pannes = logs[["event_timestamp", "machine_id", "severity" ]]


## Coûts liés aux pannes 


facto_mttr = maintenance.groupby("factory_id").agg({"mttr_hours": sum})
monthly_mttr = maintenance[["month", "factory_id", "mttr_hours"]]

production["avg_time_production"] = (production["production_cycles"] * production["avg_cycle_duration_sec"])*0.000277778
facto_production = production.groupby("factory_id").agg({"avg_time_production": sum})

month_production = production.groupby("month").agg({"avg_time_production": sum})


CA_month = ventes.groupby("month").agg({"revenue_eur": sum}).rename(columns={"revenue_eur" : "revenue_global_eur"}).reset_index()
CA_month["avg_revenue_hour"] = CA_month["revenue_global_eur"]/730


monthly_mttr = monthly_mttr.merge(CA_month, on="month", how="left")

monthly_mttr["manque_panne"]= monthly_mttr["avg_revenue_hour"] * monthly_mttr["mttr_hours"]


# Load 

# -------------------------------------------------------------------
# Connexion SQLite
# -------------------------------------------------------------------

# DB_PATH = Path("data/base.db")
# DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# engine = create_engine(
#     f"sqlite:///{DB_PATH}",
#     future=True
# )


# -------------------------------------------------------------------
# Objets pandas à publier en Silver
# -------------------------------------------------------------------

silver_objects = {
    "silver_renta_produit": renta_produit,
    "silver_top_clients": top_clients,
    "silver_sorted_sales": sorted_sales,
    "silver_global_sales": global_sales,
    "silver_facto_prod_elec_cost": facto_prod_elec_cost,
    "silver_conso_by_facto": conso_by_facto,
    "silver_all_costs_2025": all_costs_2025,
    "silver_all_costs_facto" : all_costs_facto,
    "silver_all_global_cost": all_global_cost,
    "silver_df_ca": df_ca,
    "silver_ca_month": CA_month,
    "silver_df_benef": df_benef,
    "silver_global_benef": global_benef,
    "silver_benef_produit_month": benef_produit_month,
    "silver_machines": machines,
    "silver_high_severity_total": high_severity_total,
    "silver_to_resolve_count": to_resolve_count,
    "silver_nb_pannes_global": nb_pannes_global,
    "silver_nb_pannes_high": nb_pannes_high,
    "silver_nb_pannes_medium": nb_pannes_medium,
    "silver_nb_pannes_low": nb_pannes_low,
    "silver_alerts_machines": alerts_machines,
    "silver_date_pannes": date_pannes,
    "silver_monthly_mttr": monthly_mttr,
}


# -------------------------------------------------------------------
# Fonction de conversion vers DataFrame
# -------------------------------------------------------------------

def to_dataframe(obj, object_name):
    """
    Convertit un DataFrame, une Series, une liste ou un scalaire
    en DataFrame compatible avec to_sql().
    """

    if isinstance(obj, pd.DataFrame):
        return obj.copy()

    if isinstance(obj, pd.Series):
        return obj.rename(object_name).reset_index()

    if isinstance(obj, dict):
        return pd.DataFrame([obj])

    if isinstance(obj, (list, tuple)):
        return pd.DataFrame(obj)

    # Cas d'un indicateur scalaire : nombre, chaîne, booléen, etc.
    return pd.DataFrame({
        "value": [obj]
    })


# -------------------------------------------------------------------
# Insertion des objets en Silver
# -------------------------------------------------------------------


# Insertion des objets en Silver
# -------------------------------------------------------------------

ingestion_timestamp = datetime.now(
    timezone.utc
).isoformat()

results = []

try:

    for table_name, obj in silver_objects.items():

        df_silver = to_dataframe(
            obj=obj,
            object_name=table_name
        )

        # Évite les problèmes liés à un index pandas non unique
        df_silver = df_silver.reset_index(drop=True)

        # Nettoyage minimal des noms de colonnes
        df_silver.columns = [
            str(column).strip()
            for column in df_silver.columns
        ]

        # Métadonnée de traçabilité
        df_silver["_silver_load_timestamp_utc"] = ingestion_timestamp

        # Import de la table Silver
        df_silver.to_sql(
            name=table_name,
            con=conn,
            if_exists="replace",
            index=False,
            chunksize=1_000,
            method="multi"
        )

        results.append({
            "table": table_name,
            "rows": len(df_silver),
            "columns": len(df_silver.columns),
            "status": "OK"
        })

    # Validation de toutes les opérations
    conn.commit()

except Exception as e:

    # Annulation des opérations en cas d'erreur
    conn.rollback()

    raise

finally:

    # Fermeture de la connexion SQLCipher
    conn.close()


# ingestion_timestamp = datetime.now(
#     timezone.utc
# ).isoformat()

# results = []

# with conn.begin() as connection:
#     for table_name, obj in silver_objects.items():

#         df_silver = to_dataframe(
#             obj=obj,
#             object_name=table_name
#         )

#         # Évite les problèmes liés à un index pandas non unique
#         df_silver = df_silver.reset_index(drop=True)

#         # Nettoyage minimal des noms de colonnes
#         df_silver.columns = [
#             str(column).strip()
#             for column in df_silver.columns
#         ]

#         # Métadonnée de traçabilité
#         df_silver["_silver_load_timestamp_utc"] = ingestion_timestamp

#         # Import de la table Silver
#         df_silver.to_sql(
#             name=table_name,
#             con=connection,
#             if_exists="replace",
#             index=False,
#             chunksize=1_000,
#             method="multi"
#         )

#         results.append({
#             "table": table_name,
#             "rows": len(df_silver),
#             "columns": len(df_silver.columns),
#             "status": "OK"
#         })


# -------------------------------------------------------------------
# Rapport d'import
# -------------------------------------------------------------------

rapport_import = pd.DataFrame(results)

print(rapport_import.to_string(index=False))


