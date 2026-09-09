flowchart LR
    subgraph Sources["Sources (CSV)"]
        A1[usines]
        A2[production_mensuelle]
        A3[prix_energie_marche]
        A4[stock_pieces_detachees]
        A5[qualite_mensuelle]
        A6[maintenance_mensuelle]
        A7[benchmark_industriel_externe]
        A8[ventes_contrats]
        A9[produits]
        A10[clients_industriels]
        A11[cameras_qualite]
        A12[capteurs_machines]
        A13[logs_erreurs_machines]
    end

    subgraph Extract["Extract & Normalisation"]
        B1[Chargement CSV → DataFrames pandas]
        B2[Cast IDs en str]
        B3[Parse dates (month, timestamp, event_timestamp)]
    end

    subgraph Bronze["Couche Bronze (SQLite chiffré)"]
        C1[bronze_usine]
        C2[bronze_production]
        C3[bronze_prix_ener]
        C4[bronze_stock_pieces]
        C5[bronze_qualitee]
        C6[bronze_maintenance]
        C7[bronze_benchmark]
        C8[bronze_ventes]
        C9[bronze_produit]
        C10[bronze_client]
        C11[bronze_camera]
        C12[bronze_capteurs]
        C13[bronze_logs]
    end

    subgraph Transform["Transform (Feature Engineering & Agrégats)"]
        D1[Features production & maintenance]
        D2[Rentabilité produit & top clients]
        D3[CA cumulé & ventes globales]
        D4[Coûts énergie / qualité / pièces / maintenance]
        D5[Coûts totaux par usine & globaux]
        D6[Bénéfices (mensuel, annuel, par produit)]
        D7[Machines, capteurs, caméras, logs]
        D8[Séries temporelles de pannes & coût d’immobilisation]
    end

    subgraph Silver["Couche Silver (SQLite chiffré)"]
        E1[silver_renta_produit]
        E2[silver_top_clients]
        E3[silver_sorted_sales]
        E4[silver_global_sales]
        E5[silver_all_costs_facto / all_costs_2025]
        E6[silver_all_global_cost]
        E7[silver_df_benef / global_benef / benef_produit_month]
        E8[silver_machines / high_severity / nb_pannes_*]
        E9[silver_alerts_machines / date_pannes / monthly_mttr]
        E10[... autres tables silver_*]
    end

    subgraph Metadata["Métadonnées & Rapport"]
        F1[_silver_load_timestamp_utc]
        F2[rapport_import (table, rows, columns, status)]
    end

    A1 & A2 & A3 & A4 & A5 & A6 & A7 & A8 & A9 & A10 & A11 & A12 & A13 --> B1
    B1 --> B2 --> B3
    B3 --> C1 & C2 & C3 & C4 & C5 & C6 & C7 & C8 & C9 & C10 & C11 & C12 & C13

    C1 & C2 & C3 & C4 & C5 & C6 & C7 & C8 & C9 & C10 & C11 & C12 & C13 --> D1 & D2 & D3 & D4 & D5 & D6 & D7 & D8

    D1 & D2 & D3 & D4 & D5 & D6 & D7 & D8 --> E1 & E2 & E3 & E4 & E5 & E6 & E7 & E8 & E9 & E10

    E1 & E2 & E3 & E4 & E5 & E6 & E7 & E8 & E9 & E10 --> F1 & F2
