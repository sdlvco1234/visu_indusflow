from pathlib import Path

import pandas as pd
import pandera as pa
from pandera import Column, DataFrameSchema
from datetime import datetime
import json



OUTPUT_DIR = Path("reports")
OUTPUT_DIR.mkdir(exist_ok=True)
DATA_DIR = Path("data")



def schema_usine() -> DataFrameSchema:
    return DataFrameSchema(

    {
        "factory_id": Column(pa.String, nullable=False, unique=True),
        "factory_name": Column(pa.String, nullable=False),
        "country": Column(pa.String, nullable=False),
        "city": Column(pa.String, nullable=False),
        "machine_count": Column(
            pa.Int64,
            nullable=False,
            checks=pa.Check.ge(0),
        ),
        },
        strict=True,
    )
def schema_production() -> DataFrameSchema:
    return DataFrameSchema(
       {
        "month": Column(pa.DateTime, nullable=False),
        "factory_id": Column(pa.String, nullable=False),
        "inspected_units": Column(
            pa.Int64,
            nullable=False,
            checks=pa.Check.gt(0),
        ),
        "defect_count": Column(
            pa.Int64,
            nullable=False,
            checks=pa.Check.ge(0),
        ),
        "defect_rate": Column(
            pa.Float64,
            nullable=False,
            checks=pa.Check.in_range(0, 1),
        ),
        "rework_cost_eur": Column(
            pa.Float64,
            nullable=False,
            checks=pa.Check.ge(0),
        ),
    },
    strict=True,
    coerce=False,
)


def schema_prix_energie() -> DataFrameSchema:
    return DataFrameSchema(
        {
            "month": Column(pa.DateTime),
            "country": Column(pa.String),
            "energy_price_eur_kwh": Column(pa.Float64),
        },
        strict=True,
        coerce=False,
    )


def schema_stock_pieces() -> DataFrameSchema:
    return DataFrameSchema(
        {
            "part_id": Column(pa.String),
            "factory_id": Column(pa.String),
            "part_name": Column(pa.String),
            "stock_qty": Column(pa.Int64),
            "reorder_threshold": Column(pa.Int64),
            "unit_price_eur": Column(pa.Float64),
            "avg_monthly_usage": Column(pa.Int64),
        },
        strict=True,
        coerce=False,
    )


def schema_qualite_mensuelle() -> DataFrameSchema:
    defect_rate_check = pa.Check(
    lambda df: (
        (
            df["defect_rate"]
            - df["defect_count"] / df["inspected_units"]
        ).abs() <= 1e-6
    ).all(),
    error="defect_rate ne correspond pas à defect_count / inspected_units",
    )
    return DataFrameSchema(
          {
        "month": Column(pa.DateTime, nullable=False),
        "factory_id": Column(pa.String, nullable=False),
        "inspected_units": Column(pa.Int64, checks=pa.Check.gt(0)),
        "defect_count": Column(pa.Int64, checks=pa.Check.ge(0)),
        "defect_rate": Column(pa.Float64, checks=pa.Check.in_range(0, 1)),
        "rework_cost_eur": Column(pa.Float64, checks=pa.Check.ge(0)),
    },
    checks=[defect_rate_check],
    strict=True,
    coerce=False,
    )


def schema_maintenance_mensuelle() -> DataFrameSchema:
    return DataFrameSchema(
        {
            "month": Column(pa.DateTime),
            "factory_id": Column(pa.String),
            "preventive_maintenance_count": Column(pa.Int64),
            "corrective_maintenance_count": Column(pa.Int64),
            "maintenance_cost_eur": Column(pa.Float64),
            "mttr_hours": Column(pa.Float64),
            "mtbf_hours": Column(pa.Float64),
        },
        strict=True,
        coerce=False,
    )


def schema_benchmark() -> DataFrameSchema:
    return DataFrameSchema(
        {
            "country": Column(pa.String),
            "sector_avg_oee": Column(pa.Float64),
            "sector_avg_defect_rate": Column(pa.Float64),
            "sector_avg_monthly_maintenance_cost_eur": Column(pa.Float64),
            "sector_avg_mttr_hours": Column(pa.Float64),
        },
        strict=True,
        coerce=False,
    )


def schema_ventes() -> DataFrameSchema:
    return DataFrameSchema(
        {
            "month": Column(pa.DateTime),
            "client_id": Column(pa.String),
            "product_id": Column(pa.String),
            "quantity": Column(pa.Int64),
            "revenue_eur": Column(pa.Float64),
            "contract_type": Column(pa.String),
        },
        strict=True,
        coerce=False,
    )


def schema_produit() -> DataFrameSchema:
    return DataFrameSchema(
        {
            "product_id": Column(pa.String),
            "product_name": Column(pa.String),
            "category": Column(pa.String),
            "unit_cost_eur": Column(pa.Int64),
        },
        strict=True,
        coerce=False,
    )


def schema_client() -> DataFrameSchema:
    return DataFrameSchema(
        {
            "client_id": Column(pa.String),
            "client_name": Column(pa.String),
            "sector": Column(pa.String),
            "country": Column(pa.String),
        },
        strict=True,
        coerce=False,
    )


SCHEMAS = { # ---> à modfifier pour vérifier les données de la table bronze
    "bloc5_usines": schema_usine(),
    "bloc5_produits": schema_production(),
    "bloc5_prix_energie_marche": schema_prix_energie(),
    "bloc5_stock_pieces_detachees": schema_stock_pieces(),
    "bloc5_qualite_mensuelle": schema_qualite_mensuelle(),
    "bloc5_maintenance_mensuelle": schema_maintenance_mensuelle(),
    "bloc5_benchmark_industriel_externe": schema_benchmark(),
    "bloc5_ventes_contrats": schema_ventes(),
    "bloc5_produits": schema_produit(),
    "bloc5_clients_industriels": schema_client(),
}


DATE_COLUMNS = {
    "bloc5_production_mensuelle": ["month"],
    "prix_bloc5_prix_energie_marche.csvenergie": ["month"],
    "bloc5_qualite_mensuelle": ["month"],
    "bloc5_maintenance_mensuelle": ["month"],
    "bloc5_ventes_contrats": ["month"],
}


def load_csv(table_name: str) -> pd.DataFrame:
    """Charge un CSV en essayant de gérer les formats français courants."""
    file_path = DATA_DIR / f"{table_name}.csv"

    if not file_path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {file_path}")

    return pd.read_csv(
        file_path,
        sep=",",
        encoding="utf-8-sig",
        parse_dates=DATE_COLUMNS.get(table_name, []),
    )

def dataframe_to_json_records(df: pd.DataFrame) -> list[dict]:
    """
    Convertit un DataFrame en liste de dictionnaires JSON compatibles.
    Remplace notamment les NaN par None.
    """
    df = df.astype(object).where(pd.notna(df), None)
    return df.to_dict(orient="records")


def validate_table(table_name: str) -> dict:
    """Valide une table et retourne un résultat sérialisable en JSON."""

    print(f"\n{'=' * 70}")
    print(f"Validation de la table : {table_name}")

    try:
        df = load_csv(table_name)

        # lazy=True collecte toutes les erreurs de validation.
        SCHEMAS[table_name].validate(df, lazy=True)

        print("OK - structure et types valides")
        print(
            f"Dimensions : "
            f"{df.shape[0]:,} lignes x {df.shape[1]} colonnes"
        )

        return {
            "table": table_name,
            "valid": True,
            "status": "OK",
            "rows": int(df.shape[0]),
            "columns_count": int(df.shape[1]),
            "columns": list(df.columns),
            "errors": [],
        }

    except pa.errors.SchemaErrors as error:
        print("ERREUR - données invalides")

        failure_cases = error.failure_cases.copy()

        wanted_columns = [
            "schema_context",
            "column",
            "check",
            "failure_case",
            "index",
        ]

        existing_columns = [
            column
            for column in wanted_columns
            if column in failure_cases.columns
        ]

        error_report = failure_cases[existing_columns]

        print(error_report.to_string(index=False))

        return {
            "table": table_name,
            "valid": False,
            "status": "SCHEMA_ERROR",
            "rows": None,
            "columns_count": None,
            "columns": [],
            "errors": dataframe_to_json_records(error_report),
        }

    except Exception as error:
        print(f"ERREUR DE CHARGEMENT : {error}")

        return {
            "table": table_name,
            "valid": False,
            "status": "LOAD_ERROR",
            "rows": None,
            "columns_count": None,
            "columns": [],
            "errors": [
                {
                    "type": type(error).__name__,
                    "message": str(error),
                }
            ],
        }


def validate_all_tables() -> dict:
    """Valide toutes les tables et retourne le rapport complet."""

    tables_results = {}

    for table_name in SCHEMAS:
        result = validate_table(table_name)
        tables_results[table_name] = result

    valid_tables = [
        table_name
        for table_name, result in tables_results.items()
        if result["valid"]
    ]

    invalid_tables = [
        table_name
        for table_name, result in tables_results.items()
        if not result["valid"]
    ]

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "total_tables": len(tables_results),
            "valid_tables": len(valid_tables),
            "invalid_tables": len(invalid_tables),
            "all_valid": len(invalid_tables) == 0,
        },
        "valid_tables": valid_tables,
        "invalid_tables": invalid_tables,
        "tables": tables_results,
    }

    return report


def save_validation_report(
    report: dict,
    output_path: Path,
) -> None:
    """Exporte le rapport de validation au format JSON."""

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2,
            default=str,
        )


if __name__ == "__main__":
    report = validate_all_tables()

    output_path = OUTPUT_DIR / "validation_report.json"
    save_validation_report(report, output_path)

    print(f"\nRapport JSON généré : {output_path}")
    print("\nRésumé :")
    print(f"Tables valides   : {report['summary']['valid_tables']}")
    print(f"Tables invalides : {report['summary']['invalid_tables']}")

    if not report["summary"]["all_valid"]:
        raise SystemExit("Certaines tables sont invalides.")