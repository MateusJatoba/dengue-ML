# Previsão de dengue em cidades da Bahia com aprendizado de máquina

Projeto acadêmico que usa dados públicos para antecipar, em quatro semanas, a situação da dengue em 15 cidades da Bahia.

## Finalidade

Dar às equipes de vigilância uma estimativa antecipada da dengue em cada cidade, com tempo suficiente para agir (eliminação de criadouros, reforço de equipes, preparo de unidades de saúde).

O projeto responde a duas perguntas, cada uma com um tipo de modelo:

| Pergunta | Tipo de modelo | Saída |
| --- | --- | --- |
| Quantos casos a cidade terá daqui a quatro semanas? | Regressão linear | Um número de casos |
| Em qual nível de surto a cidade estará daqui a quatro semanas? | Classificação | A probabilidade de cada nível |

As duas respostas se complementam: a regressão dimensiona o problema, e a classificação traduz o risco em um alerta fácil de comunicar.

## Tarefa 1: regressão linear

- **O que prevê:** o número de casos de dengue da cidade na semana `t + 4`, a partir do que se sabe na semana `t`.
- **Modelo:** regressão linear.
- **Alvo:** `casos_est` (casos estimados pelo InfoDengue, já corrigidos pelo atraso de notificação) quatro semanas à frente.
- **Transformação do alvo:** o número de casos é muito assimétrico (muitas semanas com poucos casos e algumas com milhares). Por isso o modelo é treinado sobre `log(1 + casos)` e a previsão é convertida de volta para casos.
- **Comparação entre cidades:** além dos casos absolutos, o resultado também é avaliado em incidência por 100 mil habitantes, para que Salvador não domine o erro.

> **Mudança em relação ao plano acima (primeiro teste).** O primeiro teste prevê a **incidência por 100 mil habitantes** quatro semanas à frente, e não os casos absolutos. O rótulo está em escala original, sem `log(1 + x)`; a transformação logarítmica segue em aberto. A classificação do nível de alerta (Tarefa 2) fica para depois deste teste. Detalhes em "Primeiro teste: base de modelagem".

## Tarefa 2: classificação

- **O que prevê:** a probabilidade de a cidade estar em cada nível de alerta na semana `t + 4`.
- **Classes:** os quatro níveis de alerta do InfoDengue (coluna `nivel`).

| Nível | Cor | Leitura no projeto |
| --- | --- | --- |
| 1 | Verde | Sem surto |
| 2 | Amarelo | Atenção: condições favoráveis à transmissão |
| 3 | Laranja | Surto: transmissão sustentada |
| 4 | Vermelho | Surto intenso: incidência alta |

- **Saída:** quatro probabilidades que somam 100%. Exemplo: verde 10%, amarelo 25%, laranja 45%, vermelho 20%.
- **Modelos comparados:** regressão logística multinomial (linha de base), Naive Bayes, KNN e gradient boosting.

A descrição exata de cada nível deve ser confirmada na documentação do InfoDengue antes da entrega.

## Dados

| Fonte | O que fornece | Acesso |
| --- | --- | --- |
| InfoDengue | Casos notificados e estimados, incidência, indicador de transmissão, nível de alerta, temperatura e umidade, por cidade e semana | API pública `https://info.dengue.mat.br/api/alertcity` |
| IBGE | Código (geocode) dos municípios | API de localidades |

**Recorte:** 15 cidades da Bahia, de 2015 a 2026, uma linha por cidade e semana epidemiológica (cerca de 9 mil linhas).

**Cidades:** Salvador, Feira de Santana, Vitória da Conquista, Camaçari, Juazeiro, Lauro de Freitas, Itabuna, Ilhéus, Porto Seguro, Barreiras, Jequié, Alagoinhas, Teixeira de Freitas, Paulo Afonso e Eunápolis. O conjunto cobre litoral úmido, semiárido, planalto e cerrado.

## Estratégias

### 1. Extração

- Script `src/extrair_infodengue.py`, que consulta a API por geocode e salva um CSV bruto por cidade.
- Lista de cidades em `data/cidades.csv`, fora do código, para facilitar inclusões e remoções.
- Cache dos arquivos brutos, novas tentativas em caso de erro e pausa entre chamadas.
- Relatório de validação ao final: semanas faltantes, duplicadas e valores ausentes.

### 2. Limpeza

- Uso de `casos_est` no lugar de `casos`, porque as notificações recentes chegam com atraso.
- Remoção de duplicatas por cidade e semana.
- Tratamento de semanas sem registro e de valores ausentes de clima.

### 3. Clima

- Temperatura e umidade vêm do próprio InfoDengue (`tempmin`, `tempmed`, `tempmax`, `umidmin`, `umidmed`, `umidmax`), sem integração com outras bases.
- **Decisão: não usar dados de chuva do INMET.** A chuva é a única variável de clima ausente no InfoDengue, mas o seu efeito sazonal é captado pela semana do ano combinada com a cidade (ver Engenharia de atributos), e a umidade do InfoDengue cobre parte da variação de cada ano. Dispensar o INMET evita baixar 12 anos de arquivos, associar cada cidade a uma estação e tratar falhas de cobertura.
- **O que isso deixa de captar:** a chuva de cada ano em relação ao padrão da época (por exemplo, um abril muito seco ou muito chuvoso). Não foi medido quanto isso afetaria o desempenho; se o tempo permitir, a chuva do INMET pode ser testada depois como um cenário extra do treino com e sem clima.

### 4. Engenharia de atributos

Todos os atributos usam apenas informação disponível na semana da previsão.

- **Histórico da doença:** casos e incidência das últimas quatro semanas, variação percentual entre semanas, indicador de transmissão e nível de alerta atual.
- **Clima defasado:** temperatura mínima e umidade das semanas anteriores, do InfoDengue. O efeito do clima sobre o mosquito demora algumas semanas para aparecer nos casos.
- **Calendário:** semana do ano, para capturar a sazonalidade, inclusive a da chuva. Para os modelos lineares e a regressão logística, codificar como seno e cosseno da semana (assim a semana 52 fica próxima da 1) e deixar o efeito variar por cidade, porque o regime de chuvas muda entre litoral e semiárido.
- **Cidade:** população e identificação da cidade.

### Primeiro teste: base de modelagem

Versão inicial e mais simples que a engenharia de atributos descrita acima, gerada por `src/construir_atributos.py` em `data/processed/base_modelagem.csv` (9.135 linhas, 15 cidades).

**Rótulo (`rotulo`):** incidência por 100 mil habitantes quatro semanas à frente, calculada por cidade como `casos_est / população mais recente × 100 mil`. O horizonte é ajustável com `--horizonte`; com `0` o rótulo vira quase uma conta a partir de `casos_est`, o que inflaria o R², por isso o padrão é 4.

**Atributos:**

| Atributo | Origem |
| --- | --- |
| `cidade` | InfoDengue (categórica) |
| `casos_est` | InfoDengue, casos estimados com correção do atraso de notificação |
| `Rt`, `receptivo`, `transmissao`, `nivel_inc` | InfoDengue |
| `tempmed`, `umidmed` | InfoDengue |
| `trimestre` | Trimestre civil (1 a 4) de `data_iniSE` |
| `estacao` | Estação do ano de `data_iniSE`, hemisfério sul |

`data_iniSE` fica na base só para a divisão temporal e não deve entrar como atributo.

**Estações do ano:** verão de 21/12 a 19/03, outono de 20/03 a 20/06, inverno de 21/06 a 22/09 e primavera de 23/09 a 20/12. As datas são fixas, mas solstícios e equinócios variam um ou dois dias entre os anos. Trimestre e estação são calculados a partir do primeiro dia (domingo) da semana epidemiológica.

**Troca de população do InfoDengue (SE 202306):** o `pop` muda em todas as cidades nessa semana (de -13% em Itabuna a +23% em Ilhéus), o que cria um degrau em `p_inc100k`. Decisão: não excluir semanas e recalcular a incidência com a população mais recente de cada cidade para toda a série. A incidência histórica fica coerente entre os anos, mas usa a população do Censo 2022 também em 2015-2022 e pode divergir da publicada na época.

**Ainda não feito neste teste:** lags e variações entre semanas, seno e cosseno da semana do ano, tratamento dos ausentes de `tempmed` e `umidmed` (4,95%, com atenção a Barreiras de 2017 a 2023), codificação de `cidade` e `estacao` e a divisão temporal.

### 5. Divisão dos dados

- Divisão temporal: anos mais antigos para treino, anos mais recentes para teste.
- Nenhuma divisão aleatória, porque misturar semanas vizinhas entre treino e teste infla o resultado.
- Qualquer estatística usada nos atributos (médias, escalas) é calculada só com o treino.

### 6. Linhas de base

Todo modelo é comparado com a regra ingênua de persistência:

- Regressão: "daqui a quatro semanas haverá o mesmo número de casos de hoje".
- Classificação: "daqui a quatro semanas o nível será o mesmo de hoje".

Um modelo só é considerado útil se superar essa regra.

### 7. Avaliação

| Tarefa | Métricas |
| --- | --- |
| Regressão | MAE, RMSE e R², em casos e em incidência por 100 mil habitantes |
| Classificação | Log loss, F1 macro, recall por nível, matriz de confusão e curva de calibração |

- Na classificação, o recall dos níveis 3 e 4 recebe atenção especial: deixar de avisar sobre um surto custa mais do que um alarme falso.
- Cada modelo é treinado com e sem as variáveis de clima, para medir quanto o clima acrescenta.

## Limitações conhecidas

- **Níveis definidos pelo InfoDengue.** As classes dependem das regras do sistema de alerta, que usam casos e clima. O modelo aprende, em parte, a reproduzir essas regras.
- **Classes desbalanceadas.** O nível 4 é raro, sobretudo nas cidades menores, o que dificulta o aprendizado e a avaliação dessa classe.
- **Regressão linear e picos.** O modelo linear tende a subestimar picos epidêmicos, mesmo com a transformação logarítmica.
- **Sem chuva medida.** A chuva é aproximada pela sazonalidade (semana do ano e cidade), o que não capta a variação de cada ano.
- **Clima do InfoDengue incompleto em parte da série.** Há 4,9% de ausentes nas médias de temperatura e umidade, e em Barreiras, de 2017 a 2023, as colunas de clima têm entre 42% e 100% de ausentes e valores implausíveis. Ainda é preciso decidir como tratar essa cidade.
- **Subnotificação.** Os casos notificados são menores que os reais, e a diferença varia entre cidades e anos.
- **População única na incidência.** O rótulo do primeiro teste usa a população do Censo 2022 em toda a série, inclusive em 2015-2022.
- **Estações com datas fixas.** O limite entre estações varia um ou dois dias entre os anos.
- **Semanas recentes.** `casos_est` das cerca de 10 últimas semanas é uma estimativa de nowcasting e pode ser revisada.

## Estrutura do projeto

```
src/
  extrair_infodengue.py   extração dos dados da API
  construir_atributos.py  atributos e rótulo do primeiro teste
data/
  cidades.csv             nome, uf e geocode das cidades
  raw/                    um CSV por cidade, como veio da API
  processed/              base consolidada e base de modelagem
requirements.txt
README.md
```

## Etapas

- [x] Definição do problema, dos alvos e das fontes
- [x] Extração dos dados do InfoDengue
- [x] Base de modelagem do primeiro teste (atributos e rótulo)
- [ ] Tratamento dos ausentes de clima e divisão temporal
- [ ] Atributos adicionais (lags, sazonalidade em seno e cosseno)
- [ ] Treino e avaliação da regressão linear
- [ ] Treino e avaliação dos classificadores
- [ ] Relatório final

## Como executar

Requer Python 3.11 ou superior.

```
pip install -r requirements.txt
python src/extrair_infodengue.py
```

Para gerar a base do primeiro teste, depois da extração:

```
python src/construir_atributos.py
python src/construir_atributos.py --horizonte 4
```

`--horizonte` é o número de semanas à frente do rótulo (padrão: 4). O resultado é `data/processed/base_modelagem.csv`.

Parâmetros opcionais da extração:

| Parâmetro | Padrão | Efeito |
| --- | --- | --- |
| `--ano-inicio` | 2015 | Primeiro ano consultado |
| `--ano-fim` | 2026 | Último ano consultado |
| `--doenca` | dengue | Doença consultada na API |
| `--forcar` | desligado | Baixa de novo mesmo que o CSV bruto já exista |

Arquivos gerados:

- `data/raw/<doenca>_<geocode>_<ano-inicio>_<ano-fim>.csv`: resposta da API, sem alteração, uma por cidade.
- `data/processed/dengue_bahia.csv` e `dengue_bahia.parquet`: base consolidada, com as colunas `geocode`, `cidade` e `uf` acrescentadas, ordenada por cidade e data.
- `data/processed/relatorio_validacao.txt`: cópia do relatório impresso ao final da execução.

Os CSVs brutos funcionam como cache. Como o ano corrente ainda recebe semanas novas e o InfoDengue revisa as semanas recentes, use `--forcar` para atualizar a base.

Para incluir ou remover cidades, edite `data/cidades.csv` (colunas `nome`, `uf`, `geocode`, em UTF-8). O geocode é o código IBGE de 7 dígitos, disponível em `https://servicodados.ibge.gov.br/api/v1/localidades/estados/29/municipios`.