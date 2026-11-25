# Dicionário de dados

Descreve as colunas da base do InfoDengue (`data/processed/dengue_bahia.csv`) e da aba `InfoDengue_semanal` de `amostra_salvador_maio_2026.xlsx`, que são as mesmas.

## Sobre a base

| Item | Valor |
| --- | --- |
| Fonte | API do InfoDengue, `https://info.dengue.mat.br/api/alertcity`, extraída em 07/10/2026 |
| Cidades | 15 cidades da Bahia, listadas em `data/cidades.csv` |
| Período | Semanas epidemiológicas de 201501 a 202639 |
| Granularidade | Uma linha por cidade e semana epidemiológica (9.195 linhas) |
| Amostra | Salvador (geocode 2927408), semanas 202617 a 202622 (26/04/2026 a 06/06/2026), as semanas que contêm algum dia de maio |

A semana epidemiológica vai de domingo a sábado. Células vazias são valores ausentes na fonte.

## Colunas

As descrições vêm do dicionário oficial do InfoDengue (`https://info.dengue.mat.br/services/api`, botão "Mostrar Dicionário de Dados"). A coluna "Observado na base" registra o que foi verificado nas 15 cidades, de 2015 a 2026. As colunas marcadas com "sem descrição oficial" não aparecem no dicionário do InfoDengue; a descrição é uma interpretação pelo nome e pelos valores.

### Identificação

| Coluna | Tipo | Descrição | Observado na base |
| --- | --- | --- | --- |
| `geocode` | inteiro | Código IBGE do município, 7 dígitos | Acrescentada pelo script de extração |
| `cidade` | texto | Nome do município, conforme `data/cidades.csv` | Acrescentada pelo script de extração |
| `uf` | texto | Sigla do estado | Acrescentada pelo script de extração; sempre `BA` |
| `data_iniSE` | data | Primeiro dia da semana epidemiológica (domingo) | Sem ausentes |
| `SE` | inteiro | Semana epidemiológica no formato AAAASS (202618 = semana 18 de 2026) | Sem ausentes nem duplicatas |
| `Localidade_id` | inteiro | Divisão submunicipal (implementada apenas no Rio de Janeiro) | Sempre 0 |
| `id` | texto | Índice numérico do registro | 18 dígitos; gravado como texto no Excel, que só preserva 15 dígitos em números |
| `versao_modelo` | texto (data) | Versão do modelo, de uso interno do InfoDengue | Data em que a linha foi calculada pela última vez |
| `municipio_nome` | texto | Nome do município segundo o InfoDengue (sem descrição oficial) | Igual a `cidade` em todas as linhas |
| `pop` | inteiro | População estimada (IBGE) | Dois valores por cidade, com troca na SE 202306; em Salvador, de 2.886.698 para 2.610.987 |

### Casos

| Coluna | Tipo | Descrição | Observado na base |
| --- | --- | --- | --- |
| `casos` | inteiro | Número de casos notificados na semana. Os valores são atualizados retroativamente toda semana | Incompleto nas semanas mais recentes por atraso de notificação |
| `casos_est` | decimal | Número estimado de casos na semana pelo modelo de nowcasting, que corrige o atraso de notificação | Só difere de `casos` nas cerca de 10 semanas mais recentes; na amostra de maio é igual a `casos` |
| `casos_est_min` | inteiro | Limite inferior do intervalo de credibilidade de 95% de `casos_est` | Igual a `casos_est` fora das semanas recentes |
| `casos_est_max` | inteiro | Limite superior do intervalo de credibilidade de 95% de `casos_est` | Igual a `casos_est` fora das semanas recentes |
| `casprov` | inteiro | Casos prováveis na semana (sem descrição oficial) | Sem ausentes; em geral menor que `casos` |
| `casprov_est` | decimal | Estimativa de casos prováveis (sem descrição oficial) | 100% vazia |
| `casprov_est_min` | decimal | Limite inferior da estimativa de casos prováveis (sem descrição oficial) | 100% vazia |
| `casprov_est_max` | decimal | Limite superior da estimativa de casos prováveis (sem descrição oficial) | 100% vazia |
| `casconf` | decimal | Casos confirmados (sem descrição oficial) | 100% vazia |
| `notif_accum_year` | inteiro | Número acumulado de casos no ano, segundo o dicionário oficial | Não se comporta como acumulado anual: é constante por cidade e igual à soma de `casos` em todo o período consultado (92.194 em Salvador). Não usar como atributo |
| `p_inc100k` | decimal | Taxa de incidência estimada por 100 mil habitantes | Sofre um degrau na SE 202306 por causa da troca de `pop` |

### Transmissão e alerta

| Coluna | Tipo | Descrição | Valores |
| --- | --- | --- | --- |
| `Rt` | decimal | Estimativa pontual do número reprodutivo dos casos. Acima de 1, a transmissão está crescendo | 0 a 18,5 na base |
| `p_rt1` | decimal | Probabilidade de `Rt` ser maior que 1. O alerta laranja exige `p_rt1` > 0,95 por 3 semanas ou mais | 0 a 1 |
| `nivel` | inteiro | Nível de alerta | 1 = verde, 2 = amarelo, 3 = laranja, 4 = vermelho |
| `receptivo` | inteiro | Receptividade climática, isto é, condições para alta capacidade vetorial | 0 = desfavorável, 1 = favorável, 2 = favorável nesta semana e na anterior, 3 = favorável por pelo menos três semanas. Na base só aparecem 0 e 1 |
| `transmissao` | inteiro | Evidência de transmissão sustentada | 0 = nenhuma, 1 = possível, 2 = provável, 3 = altamente provável. Na base só aparecem 0 e 1 |
| `nivel_inc` | inteiro | Posição da incidência estimada em relação aos limiares | 0 = abaixo do limiar pré-epidêmico, 1 = entre o pré-epidêmico e o epidêmico, 2 = acima do limiar epidêmico |

### Clima

Valores semanais calculados pelo próprio InfoDengue.

| Coluna | Tipo | Unidade | Descrição | Ausentes na base |
| --- | --- | --- | --- | --- |
| `tempmin` | decimal | °C | Média das temperaturas mínimas diárias da semana | 0,22% |
| `tempmed` | decimal | °C | Média das temperaturas diárias da semana | 4,92% |
| `tempmax` | decimal | °C | Média das temperaturas máximas diárias da semana | 4,92% |
| `umidmin` | decimal | % | Média da umidade relativa mínima diária da semana | 4,46% |
| `umidmed` | decimal | % | Média da umidade relativa diária da semana | 4,92% |
| `umidmax` | decimal | % | Média da umidade relativa máxima diária da semana | 2,14% |

Em Barreiras, de 2017 a 2023, essas colunas têm muitas ausências e valores implausíveis (umidade acima de 100%, `tempmin` acima de 30 °C). Em Salvador, no período da amostra, estão completas. Não há coluna de chuva no InfoDengue.
