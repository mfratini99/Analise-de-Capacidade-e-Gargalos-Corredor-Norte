# Case Rumo — Corredor Norte

## Objetivo

Este projeto analisa os dados operacionais e os relatos de campo do Corredor Norte para investigar fatores associados ao tempo de ciclo, às filas e à variação do volume transportado. A análise apoia a discussão entre duas alternativas:

- **CAPEX:** adicionar locomotivas e/ou vagões;
- **OPEX:** melhorar o desempenho operacional, a manutenção e/ou a capacidade de descarga.

O código combina análise exploratória, extração de eventos de texto, cruzamento por data, indicadores estatísticos, um modelo simplificado de filas e cenários hipotéticos.

> **Importante:** os resultados são limitados às informações presentes nos arquivos recebidos. O modelo não comprova, por si só, a capacidade nominal do porto nem o tamanho adequado da frota.

## Arquivos de entrada

Coloque os arquivos abaixo na mesma pasta do script:

- `Base_Operacional.csv` — base estruturada com datas, identificação dos trens, volume transportado e tempos das etapas do processo.
- `Relatorios_Campo.txt` — relatos livres sobre ocorrências operacionais, equipamentos, clima, via permanente e restrições portuárias.

O script procura os arquivos por padrões de nome (`*Base_Operacional*.csv` e `*Campo*.txt`), então os nomes podem conter prefixos ou sufixos desde que correspondam a esses padrões.

## Requisitos

- Python 3.10 ou superior (recomendado)
- pandas
- numpy
- matplotlib
- seaborn
- scipy

## Como executar

1. Instale o Python.
2. Salve o script `.py` e os dois arquivos de entrada na mesma pasta.
3. Abra um terminal nessa pasta.
4. Instale as dependências:

   ```bash
   python -m pip install pandas numpy matplotlib seaborn scipy
   ```

5. Execute o script:

   ```bash
   analise_corredor_norte.py
   ```

O script usa uma semente aleatória fixa (`42`) para favorecer a reprodutibilidade.

## Etapas da análise

### 1. Carregamento e qualidade da base

O código lê a base operacional, converte `Data_Partida` para data, remove linhas duplicadas e registros sem identificação do trem ou data. Em seguida, calcula verificações de qualidade, incluindo:

- quantidade de registros e dias;
- quantidade de trens registrados por dia;
- percentual de viagens com volume igual a 12.100 toneladas;
- repetição dos vetores de tempos das etapas;
- divergências entre `Tempo_Ciclo_Total` e a soma das etapas consideradas.

Essas verificações são diagnósticos da base, não garantias de que todos os dados estejam corretos.

### 2. Extração e classificação dos relatos de campo

O arquivo de texto é dividido em blocos de ocorrência. O script normaliza os textos — convertendo para minúsculas e removendo acentos — e usa expressões regulares e palavras-chave para classificar cada relato em categorias, como:

- Restrição do porto;
- Clima (Serra);
- Via permanente;
- Equipamento do terminal;
- Material rodante;
- Sistemas e pátio (tendência);
- Dia normal (controle);
- Outros.

As datas são extraídas de formatos previstos no código. A classificação é baseada em regras: não é um sistema de compreensão automática de linguagem, e pode exigir revisão manual se o formato dos relatórios mudar.

### 3. Cruzamento e estimativa de impacto

As datas dos relatos são cruzadas com a data normalizada da base operacional. Para cada evento, o código compara os indicadores do dia com uma linha de base composta pelos dias sem incidentes classificados.

São calculados, entre outros:

- tempo médio de ciclo no dia do evento;
- variação percentual do ciclo em relação à linha de base;
- estimativa de horas adicionais de ativo;
- toneladas equivalentes estimadas;
- diferença média de tempo em cada etapa;
- teste de Mann–Whitney para comparar os tempos de ciclo entre os grupos.

O teste estatístico deve ser interpretado com cautela: há poucos eventos, as observações podem não ser independentes e os grupos podem diferir por outros fatores. As toneladas equivalentes são uma estimativa construída a partir das premissas do código, não uma medição direta de carga perdida.

### 4. Teoria das filas e capacidade

O script calcula indicadores simplificados a partir do número de trens observados por dia, do tempo médio de descarga e do tempo de ciclo. Também utiliza relações inspiradas na Lei de Little e em um modelo de gargalo para explorar a relação entre frota, vazão e fila.

O modelo assume uma posição de descarga para calcular a taxa de atendimento (`mu = 24 / tempo médio de descarga`). **Essa é uma hipótese de modelagem, não uma informação confirmada sobre a configuração real do porto.** A base não especifica o número de posições de descarga, a capacidade nominal do porto nem todos os limites de cada etapa.

Por isso, os resultados devem ser apresentados como um cenário simplificado e condicional, e não como prova definitiva de que o porto é o gargalo real.

### 5. Variabilidade do tempo de ciclo

O código calcula os percentis P50, P90, P95 e P99 do tempo de ciclo e estima a capacidade correspondente usando a frota inferida pelo modelo. Essa comparação ilustra como ciclos mais longos reduzem a capacidade estimada para uma frota fixa.

A frota em circulação é inferida a partir da vazão observada e do ciclo médio. Ela não equivale necessariamente ao tamanho total da frota física da companhia.

### 6. Cenários CAPEX e OPEX

O script compara cenários com acréscimo hipotético de trens e cenários com melhorias hipotéticas na taxa de descarga (5%, 10%, 15% e 20%). Os ganhos em toneladas são estimados para o período observado e extrapolados para 365 dias.

Esses percentuais são hipóteses para análise de sensibilidade, não previsões confirmadas. A extrapolação anual pressupõe que o comportamento do período observado se mantenha ao longo do ano. O código não inclui valores de investimento, custos operacionais, receitas ou margens; portanto, não calcula ROI, VPL ou payback.

## Arquivos de saída

Ao terminar, o script gera os seguintes arquivos no diretório de execução:

- `fig1_frota_vs_fila.png` — vazão e fila estimadas em função do número de trens;
- `fig2_perda_por_evento.png` — estimativa de horas de ativo perdidas por etapa e ocorrência;
- `fig3_capacidade_percentil.png` — capacidade estimada da frota por percentil do ciclo;
- `fig4_capacidade_percentil_ton.png` — capacidade estimada da frota por percentil das toneladas do ciclo;
- `fig5_pareto_horas.png` — gráfico de Pareto do impacto das horas em porcentagem;
- `results.json` — indicadores de qualidade, eventos extraídos, impactos estimados, resultados do modelo, cenários e limitações.

## Limitações e cuidados de interpretação

1. **Cobertura da base:** os logs mencionam uma programação de 12 trens por dia, enquanto a base pode apresentar seis registros por dia. Não é possível afirmar, somente com os arquivos, se a base representa toda a operação ou apenas uma parte dela.
2. **Volume por viagem:** o código verifica a frequência de registros com 12.100 toneladas, mas esse valor não deve ser tratado automaticamente como capacidade nominal sem documentação adicional.
3. **Eventos e causalidade:** a coincidência temporal entre um evento e um indicador ruim não prova que o evento tenha causado toda a diferença.
4. **Linha de base:** a comparação entre dias com e sem relatos depende da classificação dos logs e pode ser afetada por diferenças entre períodos.
5. **Modelo de filas:** a hipótese de uma posição de descarga pode não representar a operação real. A fila estimada é sensível a essa premissa e às simplificações do modelo.
6. **CAPEX versus OPEX:** sem dados confiáveis de frota disponível, capacidade por etapa, custos e demanda, não é possível declarar de forma definitiva qual alternativa tem melhor retorno financeiro.
7. **Extrapolação anual:** a projeção para 365 dias é indicativa e pressupõe estabilidade das condições operacionais.
8. **Validação técnica:** revise os resultados e as premissas antes de utilizá-los em uma apresentação executiva.


## Reprodutibilidade e privacidade

- Execute o script a partir de uma pasta que contenha os arquivos de entrada.
- Mantenha os nomes das colunas esperados pelo código.
- Se os dados forem confidenciais ou de uso interno, não publique as bases em um repositório público sem autorização. Nesse caso, publique o código e uma amostra anonimizada, ou mantenha o repositório privado.
- Registre quaisquer alterações nas regras de classificação, nas premissas e nos parâmetros dos cenários.
