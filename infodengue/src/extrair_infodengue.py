"""Extrai os dados semanais do InfoDengue para as cidades de data/cidades.csv.

Salva um CSV bruto por cidade em data/raw/, gera a base consolidada em
data/processed/ e imprime um relatório de validação.

Uso:
    python src/extrair_infodengue.py
    python src/extrair_infodengue.py --ano-inicio 2015 --ano-fim 2026 --forcar
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import requests

URL_API = "https://info.dengue.mat.br/api/alertcity"

RAIZ = Path(__file__).resolve().parent.parent
ARQ_CIDADES = RAIZ / "data" / "cidades.csv"
DIR_BRUTO = RAIZ / "data" / "raw"
DIR_PROCESSADO = RAIZ / "data" / "processed"

# Nomes das colunas como a API devolve.
COL_DATA = "data_iniSE"
COL_SEMANA = "SE"
COL_CASOS = "casos"

TIMEOUT_S = 60
TENTATIVAS = 3
ESPERA_BASE_S = 5
PAUSA_ENTRE_CIDADES_S = 1

log = logging.getLogger("extrair_infodengue")


def ler_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Baixa os dados semanais do InfoDengue das cidades de data/cidades.csv."
    )
    parser.add_argument("--ano-inicio", type=int, default=2015, help="primeiro ano (padrão: 2015)")
    parser.add_argument("--ano-fim", type=int, default=2026, help="último ano (padrão: 2026)")
    parser.add_argument("--doenca", default="dengue", help="doença consultada (padrão: dengue)")
    parser.add_argument(
        "--forcar", action="store_true", help="baixa de novo mesmo que o CSV bruto já exista"
    )
    args = parser.parse_args()
    if args.ano_inicio > args.ano_fim:
        parser.error("--ano-inicio não pode ser maior que --ano-fim")
    return args


def ler_cidades() -> pd.DataFrame:
    if not ARQ_CIDADES.exists():
        raise FileNotFoundError(f"Arquivo de cidades não encontrado: {ARQ_CIDADES}")
    # utf-8-sig aceita o arquivo com ou sem BOM (o Excel grava com BOM).
    cidades = pd.read_csv(ARQ_CIDADES, encoding="utf-8-sig", dtype={"geocode": "Int64"})
    faltando = {"nome", "uf", "geocode"} - set(cidades.columns)
    if faltando:
        raise ValueError(f"{ARQ_CIDADES.name} sem as colunas: {sorted(faltando)}")
    cidades = cidades.dropna(subset=["geocode"])
    repetidos = cidades.loc[cidades["geocode"].duplicated(), "geocode"].tolist()
    if repetidos:
        raise ValueError(f"{ARQ_CIDADES.name} com geocode repetido: {repetidos}")
    return cidades.astype({"geocode": "int64"})


def ler_csv_bruto(conteudo: bytes) -> pd.DataFrame:
    """Lê o CSV da API e garante que ele tem o formato esperado."""
    dados = pd.read_csv(io.BytesIO(conteudo))
    faltando = {COL_DATA, COL_SEMANA, COL_CASOS} - set(dados.columns)
    if faltando:
        raise ValueError(f"resposta sem as colunas esperadas: {sorted(faltando)}")
    if dados.empty:
        raise ValueError("resposta sem nenhuma linha de dados")
    return dados


def baixar(geocode: int, doenca: str, ano_inicio: int, ano_fim: int) -> bytes:
    """Baixa o CSV de uma cidade, com novas tentativas e espera crescente."""
    parametros = {
        "geocode": geocode,
        "disease": doenca,
        "format": "csv",
        "ew_start": 1,
        "ew_end": 53,
        "ey_start": ano_inicio,
        "ey_end": ano_fim,
    }
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = requests.get(URL_API, params=parametros, timeout=TIMEOUT_S)
            resposta.raise_for_status()
            ler_csv_bruto(resposta.content)
            return resposta.content
        except (requests.RequestException, ValueError) as erro:
            if tentativa == TENTATIVAS:
                raise RuntimeError(f"{TENTATIVAS} tentativas sem sucesso; último erro: {erro}") from erro
            espera = ESPERA_BASE_S * tentativa
            log.warning(
                "Tentativa %d/%d falhou para %s (%s). Nova tentativa em %d s.",
                tentativa, TENTATIVAS, geocode, erro, espera,
            )
            time.sleep(espera)
    raise AssertionError("inalcançável")


def extrair(cidades: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, dict[str, str]]:
    """Devolve a base consolidada e as cidades que falharam (nome -> erro)."""
    DIR_BRUTO.mkdir(parents=True, exist_ok=True)
    partes: list[pd.DataFrame] = []
    falhas: dict[str, str] = {}
    ja_baixou = False

    for i, cidade in enumerate(cidades.itertuples(index=False), start=1):
        # O período faz parte do nome para o cache não servir dados de outro intervalo.
        arquivo = DIR_BRUTO / f"{args.doenca}_{cidade.geocode}_{args.ano_inicio}_{args.ano_fim}.csv"
        prefixo = f"[{i}/{len(cidades)}] {cidade.nome} ({cidade.geocode})"
        try:
            if arquivo.exists() and not args.forcar:
                log.info("%s: usando cache %s", prefixo, arquivo.name)
            else:
                if ja_baixou:
                    time.sleep(PAUSA_ENTRE_CIDADES_S)
                ja_baixou = True
                log.info("%s: baixando...", prefixo)
                arquivo.write_bytes(baixar(cidade.geocode, args.doenca, args.ano_inicio, args.ano_fim))
            dados = ler_csv_bruto(arquivo.read_bytes())
        except Exception as erro:  # uma cidade com problema não interrompe as demais
            log.error("%s: FALHOU - %s", prefixo, erro)
            falhas[cidade.nome] = str(erro)
            continue

        dados.insert(0, "geocode", cidade.geocode)
        dados.insert(1, "cidade", cidade.nome)
        dados.insert(2, "uf", cidade.uf)
        partes.append(dados)
        log.info("%s: %d semanas", prefixo, len(dados))

    if not partes:
        return pd.DataFrame(), falhas

    base = pd.concat(partes, ignore_index=True)
    base[COL_DATA] = pd.to_datetime(base[COL_DATA])
    base = base.sort_values(["cidade", COL_DATA], kind="stable").reset_index(drop=True)
    return base, falhas


def semanas_faltantes(datas: pd.Series) -> list[str]:
    """Semanas ausentes entre a primeira e a última semana da cidade."""
    esperadas = pd.date_range(datas.min(), datas.max(), freq="7D")
    return [d.strftime("%Y-%m-%d") for d in esperadas.difference(pd.DatetimeIndex(datas))]


def montar_relatorio(
    base: pd.DataFrame, duplicadas: pd.DataFrame, falhas: dict[str, str], args: argparse.Namespace
) -> str:
    linhas = [
        "=" * 78,
        f"RELATÓRIO DE VALIDAÇÃO - {args.doenca}, {args.ano_inicio} a {args.ano_fim}",
        "=" * 78,
    ]

    if base.empty:
        linhas.append("Nenhum dado disponível.")
    else:
        por_cidade = base.groupby("cidade")
        resumo = pd.DataFrame(
            {
                "linhas": por_cidade.size(),
                "primeira_semana": por_cidade[COL_DATA].min().dt.strftime("%Y-%m-%d"),
                "ultima_semana": por_cidade[COL_DATA].max().dt.strftime("%Y-%m-%d"),
                "se_inicial": por_cidade[COL_SEMANA].min(),
                "se_final": por_cidade[COL_SEMANA].max(),
            }
        )
        linhas += ["", "1. Linhas e período por cidade", resumo.to_string()]

        faltantes = {nome: semanas_faltantes(grupo[COL_DATA]) for nome, grupo in por_cidade}
        dup_por_cidade = duplicadas.groupby("cidade").size() if not duplicadas.empty else pd.Series(dtype=int)
        integridade = pd.DataFrame(
            {
                "semanas_faltantes": {nome: len(lista) for nome, lista in faltantes.items()},
                "linhas_duplicadas": dup_por_cidade,
            }
        ).fillna(0).astype(int)
        linhas += ["", "2. Semanas faltantes ou duplicadas por cidade", integridade.to_string()]
        for nome, lista in faltantes.items():
            if lista:
                linhas.append(f"   {nome} - faltantes: {', '.join(lista)}")
        if not duplicadas.empty:
            linhas.append("   Duplicadas removidas da base consolidada (mantida a primeira ocorrência):")
            linhas.append(duplicadas[["cidade", COL_SEMANA]].to_string(index=False))

        ausentes = (base.isna().mean() * 100).round(2).rename("pct_ausente")
        linhas += ["", "3. Percentual de valores ausentes por coluna", ausentes.to_string()]

        casos = pd.DataFrame(
            {
                "total_casos": por_cidade[COL_CASOS].sum(),
                "pct_semanas_zero_caso": por_cidade[COL_CASOS].apply(lambda s: (s == 0).mean() * 100).round(2),
            }
        )
        linhas += ["", f"4. Total de casos e semanas com zero caso (coluna '{COL_CASOS}')", casos.to_string()]

    linhas += ["", "5. Cidades que falharam no download"]
    if falhas:
        linhas += [f"   {nome}: {erro}" for nome, erro in falhas.items()]
    else:
        linhas.append("   Nenhuma.")
    linhas.append("=" * 78)
    return "\n".join(linhas)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    args = ler_argumentos()

    cidades = ler_cidades()
    log.info("%d cidades em %s", len(cidades), ARQ_CIDADES.name)

    base, falhas = extrair(cidades, args)

    duplicadas = pd.DataFrame()
    if not base.empty:
        chave = ["geocode", COL_SEMANA]
        duplicadas = base[base.duplicated(chave, keep="first")]
        if not duplicadas.empty:
            log.warning("%d linhas duplicadas (cidade e semana) removidas.", len(duplicadas))
            base = base.drop_duplicates(chave, keep="first").reset_index(drop=True)

        DIR_PROCESSADO.mkdir(parents=True, exist_ok=True)
        nome_base = f"{args.doenca}_bahia"
        base.to_csv(DIR_PROCESSADO / f"{nome_base}.csv", index=False, encoding="utf-8")
        base.to_parquet(DIR_PROCESSADO / f"{nome_base}.parquet", index=False)
        log.info("Base consolidada salva em %s (%d linhas, %d colunas)", DIR_PROCESSADO, *base.shape)

    relatorio = montar_relatorio(base, duplicadas, falhas, args)
    if not base.empty:
        (DIR_PROCESSADO / "relatorio_validacao.txt").write_text(relatorio + "\n", encoding="utf-8")
    # O console do Windows nem sempre usa UTF-8.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(relatorio)

    return 1 if base.empty else 0


if __name__ == "__main__":
    sys.exit(main())
