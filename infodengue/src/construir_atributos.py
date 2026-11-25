"""Monta a base de modelagem a partir de data/processed/dengue_bahia.parquet.

Rótulo: incidência por 100 mil habitantes (casos_est / população recente x 100 mil, no lugar
de p_inc100k, que tem um degrau na SE 202306) daqui a --horizonte semanas.
Atributos: cidade, casos_est, Rt, receptivo, transmissao, nivel_inc, tempmed, umidmed,
trimestre e estacao (calculados a partir de data_iniSE).

Uso:
    python src/construir_atributos.py
    python src/construir_atributos.py --horizonte 4
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
ARQ_ENTRADA = RAIZ / "data" / "processed" / "dengue_bahia.parquet"
ARQ_SAIDA = RAIZ / "data" / "processed" / "base_modelagem.csv"

ATRIBUTOS_BASE = [
    "cidade", "casos_est", "Rt", "receptivo", "transmissao", "nivel_inc", "tempmed", "umidmed",
]


def trimestre(data: pd.Series) -> pd.Series:
    """Trimestre do ano civil (1 a 4)."""
    return data.dt.quarter


def estacao(data: pd.Series) -> pd.Series:
    """Estação do ano no hemisfério sul, pelas datas usuais do calendário brasileiro.

    Verão: 21/12 a 19/03. Outono: 20/03 a 20/06. Inverno: 21/06 a 22/09.
    Primavera: 23/09 a 20/12. Os solstícios e equinócios variam um dia ou dois de
    um ano para o outro; aqui as datas são fixas.
    """
    md = data.dt.month * 100 + data.dt.day
    return pd.Series(
        pd.cut(
            md,
            bins=[0, 319, 620, 922, 1220, 1231],
            labels=["verao", "outono", "inverno", "primavera", "verao_fim"],
            ordered=False,
        )
        .astype(str)
        .replace({"verao_fim": "verao"}),
        index=data.index,
    )


def construir(horizonte: int) -> pd.DataFrame:
    base = pd.read_parquet(ARQ_ENTRADA).sort_values(["cidade", "data_iniSE"]).reset_index(drop=True)

    df = base[["data_iniSE", *ATRIBUTOS_BASE]].copy()
    df["trimestre"] = trimestre(df["data_iniSE"])
    df["estacao"] = estacao(df["data_iniSE"])
    # O InfoDengue trocou a população na SE 202306, o que cria um degrau em p_inc100k.
    # A incidência é recalculada com a população mais recente de cada cidade para toda a série.
    pop_ref = base.groupby("cidade")["pop"].transform("last")
    incidencia = base["casos_est"] / pop_ref * 1e5
    df["rotulo"] = incidencia.groupby(base["cidade"]).shift(-horizonte)

    return df.dropna(subset=["rotulo"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monta a base de atributos e rótulo.")
    parser.add_argument(
        "--horizonte",
        type=int,
        default=4,
        help="semanas à frente do rótulo (padrão: 4; 0 usa a incidência da própria semana)",
    )
    args = parser.parse_args()

    df = construir(args.horizonte)
    df.to_csv(ARQ_SAIDA, index=False)

    print(f"Linhas: {len(df)} | cidades: {df['cidade'].nunique()} | horizonte: {args.horizonte} semanas")
    print(f"Período (data_iniSE): {df['data_iniSE'].min().date()} a {df['data_iniSE'].max().date()}")
    print("\nAusentes por coluna (%):")
    print((df.isna().mean() * 100).round(2).to_string())
    print("\nLinhas por estação:")
    print(df["estacao"].value_counts().to_string())
    print("\nLinhas por trimestre:")
    print(df["trimestre"].value_counts().sort_index().to_string())
    print(f"\nSalvo em {ARQ_SAIDA}")


if __name__ == "__main__":
    main()
