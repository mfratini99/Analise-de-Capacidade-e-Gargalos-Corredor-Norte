# -*- coding: utf-8 -*-
"""
Created on Wed Oct 20 14:55:59 2026

@author: Marcelo Fratini
"""

# =============================================================================
# CASE RUMO - CORREDOR NORTE 
#
#  A. Extrair eventos dos logs (texto) e ruzar com a base por data; quantificar a perda de capacidade de cada evento -> ETAPAS 2 e 3
#  B. Capacidade real com percentis e variabilidade; "mais ativos resolvem ou só aumentam a fila no porto?" -> ETAPAS 4A, 4B e B
#  C. Diagnóstico, gráfico-chave, recomendação com ganho estimado -> ETAPA C, 5 e results.json
#
# =============================================================================
import glob
import json
import os
import re
import unicodedata

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as plt_seaborn
from scipy import stats

plt_seaborn.set_theme(style="whitegrid")   # visual dos gráficos
np.random.seed(42)                          # reprodutibilidade

PASTA = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()


def achar_arquivo(padrao):
    """Encontrar o txt na pasta"""
    achados = glob.glob(os.path.join(PASTA, padrao)) or glob.glob(padrao)
    if not achados:
        raise FileNotFoundError(f"Não achei '{padrao}' em {PASTA}.")
    return achados[0]


# =============================================================================
# ETAPA 1 - CARREGAR A BASE OPERACIONAL E ANALISAR A QUALIDADE DA BASE
# =============================================================================

print(" Carregando a Base Operacional e checando a qualidade...")


# IDENTIFICANDO E SEPARANDO AS COLUNAS

df = pd.read_csv(achar_arquivo("*Base_Operacional*.csv"), parse_dates=["Data_Partida"])
col_data, col_trem, col_volume = "Data_Partida", "ID_Trem", "Volume_Toneladas"
col_ciclo, col_fila, col_descarga = "Tempo_Ciclo_Total", "Tempo_Fila_Porto", "Tempo_Descarga"
ETAPAS = ["Tempo_Transito_Ida", "Tempo_Fila_Porto", "Tempo_Descarga", "Tempo_Retorno_Vazio"]
NOME = {"Tempo_Transito_Ida": "Trânsito", "Tempo_Fila_Porto": "Fila no porto",
        "Tempo_Descarga": "Descarga", "Tempo_Retorno_Vazio": "Retorno vazio"}

df["data_dia"] = df[col_data].dt.normalize()          #chave do cruzamento
df = df.drop_duplicates().dropna(subset=[col_trem, col_data])

# Checagens da qualidade
repetido = df[ETAPAS].round(2).astype(str).agg("|".join, axis=1).duplicated()
qualidade = {
    "registros": int(len(df)), "dias": int(df["data_dia"].nunique()),
    "trens_por_dia": sorted(df.groupby("data_dia").size().unique().tolist()),
    "pct_viagens_no_teto_12100t": round(float((df[col_volume] == 12100).mean() * 100), 1),
    "pct_linhas_com_vetor_de_tempos_repetido": round(float(repetido.mean() * 100), 1),
    "ciclo_difere_da_soma_das_etapas": int(((df[ETAPAS].sum(axis=1) - df[col_ciclo]).abs() > 0.05).sum()),
}
print("\n--> Qualidade da base:", qualidade)

# =============================================================================
# ETAPA 2 - MINERAÇÃO DO TXT (LOGS DE CAMPO)
# =============================================================================


print("\n--> Leitura dos Relatórios de Campo (TXT)...")

with open(achar_arquivo("*Campo*.txt"), "r", encoding="utf-8") as f:
    texto_bruto = f.read()


def normalizar(txt):
    """Minúsculas e sem acentos, para as palavras-chave casarem sempre."""
    txt = unicodedata.normalize("NFKD", txt.lower())
    return "".join(c for c in txt if not unicodedata.combining(c))


MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}

def parse_data(cabecalho):
    """Converte todos os formatos do log por regex """
    c = normalizar(cabecalho)
    m = re.search(r"(\d{1,2}) de ([a-z]+) de (\d{4})", c)
    if m and m.group(2) in MESES:
        return pd.Timestamp(int(m.group(3)), MESES[m.group(2)], int(m.group(1)))
    m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", c)
    if m:
        ano = int(m.group(3)) + (2000 if int(m.group(3)) < 100 else 0)
        return pd.Timestamp(ano, int(m.group(2)), int(m.group(1)))
    return pd.NaT


# Cada entrada do log começa com '[' no início da linha. 
blocos = [b for b in re.split(r"\n(?=\[)", texto_bruto) if b.startswith("[")]

# Regras por ordem de prioridade (a primeira que casar vence): do mais específico ao mais genérico.
REGRAS = [
    ("Restrição do porto",           r"balanca rodoviaria|navio|armazem|silo"),
    ("Clima (Serra)",                r"chuva torrencial|operacao suspensa"),
    ("Via permanente",               r"trilho|interdicao"),
    ("Equipamento do terminal",      r"moega|grade de descarga"),
    ("Material rodante",             r"locomotiva|sensor de tracao"),
    ("Sistemas e pátio (tendência)", r"sinalizacao|software|manobra"),
    ("Dia normal (controle)",        r"operacao normal|tempo seco"),
]
DONO = {"Restrição do porto": "Terceiro (porto)", "Clima (Serra)": "Externo",
        "Via permanente": "Interno", "Equipamento do terminal": "Interno",
        "Material rodante": "Interno", "Sistemas e pátio (tendência)": "Interno",
        "Dia normal (controle)": "-"}

linhas = []
for bloco in blocos:
    cabecalho, _, corpo = bloco.partition("]")
    texto_norm = normalizar(bloco)
    categoria = next((c for c, rx in REGRAS if re.search(rx, texto_norm)), "Outros")
    linhas.append({"data": parse_data(cabecalho), "categoria": categoria, "responsavel": DONO.get(categoria, "-")})
df_log = pd.DataFrame(linhas).sort_values("data").reset_index(drop=True)
print(df_log.to_string(index=False))
assert df_log["data"].notna().all() and len(df_log) == 9, "Leitura do log incompleta!"

# Dias com incidente real 
eh_incidente = ~df_log["categoria"].isin(["Dia normal (controle)", "Sistemas e pátio (tendência)"])
dias_incidente = set(df_log.loc[eh_incidente, "data"])

# =============================================================================
# ETAPA 3 - CRUZAMENTO E IMPACTO POR EVENTO
# =============================================================================
print("\n--> Cruzamento com a base e impacto de cada evento...")

# Base de comparação ("operação normal") = todos os dias sem incidente
normal = df[~df["data_dia"].isin(dias_incidente)]
base = normal[[col_ciclo, col_volume] + ETAPAS].mean()

linhas_impacto = []
for _, ev in df_log[eh_incidente].iterrows():
    d = df[df["data_dia"] == ev["data"]]                       # as 6 viagens do dia do evento
    horas = float((d[col_ciclo] - base[col_ciclo]).sum())      # horas de ativo a mais gastas
    ton_carga = float((base[col_volume] - d[col_volume]).sum())  # carga que deixou de ir
    linha = {"data": ev["data"].date().isoformat(), "categoria": ev["categoria"], "responsavel": ev["responsavel"],
             "ciclo_medio_h": round(d[col_ciclo].mean(), 1),
             "delta_ciclo_pct": round((d[col_ciclo].mean() / base[col_ciclo] - 1) * 100, 1),
             "horas_ativo_perdidas": round(horas, 1),
             # tonelada equivalente = carga perdida + o que as horas perdidas teriam transportado
             "ton_equivalentes": round(ton_carga + horas / base[col_ciclo] * base[col_volume], 0),
             "p_valor": round(float(stats.mannwhitneyu(d[col_ciclo], normal[col_ciclo]).pvalue), 4)}
    for e in ETAPAS:                                           # em qual etapa o tempo se perdeu
        linha["delta_" + NOME[e]] = round(float(d[e].mean() - base[e]), 1)
    linhas_impacto.append(linha)
df_impacto = pd.DataFrame(linhas_impacto)
print(df_impacto.to_string(index=False))
horas_total = float(df_impacto.loc[df_impacto["horas_ativo_perdidas"] > 0, "horas_ativo_perdidas"].sum())
print(f"\nTotal de horas de ativo perdidas nos incidentes: {horas_total:.0f} h")

# Correlação de Spearman 
rho_fc, p_fc = stats.spearmanr(df[col_fila], df[col_ciclo])
print(f"Spearman fila x ciclo = {rho_fc:.2f} (p={p_fc:.4f})")

# =============================================================================
# ETAPA 4A - TEORIA DAS FILAS (GARGALO E UTILIZAÇÃO)
# =============================================================================
print("--> Teoria das filas: onde está o gargalo?")

lam = len(df) / df["data_dia"].nunique()                # λ: trens/dia que chegam ao porto
S_med = df[col_descarga].mean()                         # tempo médio de descarga (h)
mu = 24.0 / S_med                                       # μ: trens/dia que 1 posição descarrega
rho = lam / mu                                          # utilização
print(f" - λ = {lam:.2f} | μ = {mu:.2f} trens/dia | ρ = {rho:.3f}")


#   1) Lei de Little: trens em circulação N = vazão x ciclo
#   2) Lei do gargalo: a vazão nunca passa de μ (o porto descarrega, no máximo, μ trens/dia)
#   D = tempo do ciclo SEM fila (trânsito + descarga + retorno): é o ciclo que um trem teria se o porto estivesse livre.
D = float((df[col_ciclo] - df[col_fila]).mean())
N_frota = lam * df[col_ciclo].mean() / 24                # trens em circulação hoje (Little)
N_sat = mu * D / 24                                      # frota a partir da qual o porto satura


def vazao_modelo(N, mu_=None, D_=None):
    """Vazão (trens/dia) de uma frota de N trens: limitada pela frota (N*24/D) e pelo porto (μ)."""
    return min(N * 24 / (D_ or D), mu_ or mu)


def fila_modelo(N):
    """Fila média (h) esperada: com o porto saturado, o ciclo vira N/μ e a fila é o que passa de D."""
    return max(0.0, N * 24 / mu - D)


print(f" - Ciclo sem fila D = {D:.1f} h | frota que satura o porto = {N_sat:.1f} trens | frota atual = {N_frota:.1f}")
print(f" - Validação: fila prevista com {N_frota:.1f} trens = {fila_modelo(N_frota):.1f} h x fila observada = {df[col_fila].mean():.1f} h")

# =============================================================================
# ETAPA 4B - CAPACIDADE REAL COM PERCENTIS (variabilidade)
# =============================================================================
print("\n--> Capacidade real: percentis do ciclo...")

# Lei de Little: trens em circulação = vazão x ciclo médio. Se o ciclo piora para o P90, a mesma frota entrega menos trens/dia.
percentis = {f"P{q}": float(np.percentile(df[col_ciclo], q)) for q in (50, 90, 95, 99)}
cap_trens_dia = {k: round(float(N_frota * 24 / v), 2) for k, v in percentis.items()}
vol_medio = float(df[col_volume].mean())
cap_ton_dia = {k: round(v * vol_medio, 0) for k, v in cap_trens_dia.items()}
print(f" - Frota em circulação: {N_frota:.1f} trens")
print(f" - Ciclo (h): { {k: round(v, 1) for k, v in percentis.items()} }")
print(f" - Capacidade da frota (trens/dia): {cap_trens_dia}")
print(f" - Capacidade da frota (ton/dia):   {cap_ton_dia}")

# =============================================================================
# ETAPA B - HIPÓTESE COMERCIAL: MAIS ATIVOS RESOLVEM OU SÓ AUMENTAM A FILA?
# =============================================================================
print("\n-->  Mais ativos resolvem o volume ou só aumentam a fila?")

teto_ganho_pct = (mu / lam - 1) * 100       # o máximo que o porto permite sobre a vazão de hoje
tabela_frota = []
for extra in (0, 2, 4):
    N = N_frota + extra
    tabela_frota.append({"trens_a_mais": extra, "vazao_trens_dia": round(vazao_modelo(N), 2), "fila_h": round(fila_modelo(N), 1)})
    print(f"   +{extra} trens: vazão {vazao_modelo(N):.2f} trens/dia | fila {fila_modelo(N):.1f} h")
print(f" - Cada trem extra acrescenta ~{S_med:.1f} h de fila (um tempo de descarga) e a vazão fica presa em μ = {mu:.2f}.")
print(f" - Ganho máximo de vazão comprando trens: +{teto_ganho_pct:.1f}% sobre os {lam:.2f} trens/dia de hoje.")

# =============================================================================
# ETAPA C - GANHO ESTIMADO DA ALAVANCA OPEX 
# =============================================================================
print("\n-->  Ganho estimado: descarga mais rápida no porto (OPEX)...")

vol_medio = float(df[col_volume].mean())
base_modelo = vazao_modelo(N_frota)
linhas_ganho = []
for p in (0.05, 0.10, 0.15, 0.20):
    mu_novo = mu * (1 + p)
    D_novo = D - S_med * p / (1 + p)
    X_novo = vazao_modelo(N_frota, mu_novo, D_novo)
    linhas_ganho.append({"ganho_descarga_pct": int(p * 100), "trens_dia": round(X_novo, 2),
                         "ganho_vazao_pct": round((X_novo / base_modelo - 1) * 100, 1),
                         "ton_a_mais_no_periodo_61d": round((X_novo - base_modelo) * vol_medio * df["data_dia"].nunique(), 0),
                         "ton_a_mais_por_ano": round((X_novo - base_modelo) * vol_medio * 365, 0)})
df_ganho = pd.DataFrame(linhas_ganho)
print(df_ganho.to_string(index=False))
print(f" Comparação: comprar trens rende no máximo +{teto_ganho_pct:.1f}% e aumenta a fila; liberar o porto rende mais, sem fila nova.")

# =============================================================================
# ETAPA 5 - GRÁFICOS 
# =============================================================================
print("\n--> Gerando os 5 gráficos e results.json...")

# Gráfico 1: por que mais trens só enchem a fila (vazão e fila em função do tamanho da frota)
Ns = np.linspace(8, 16, 100)
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
ax[0].plot(Ns, [vazao_modelo(n) for n in Ns], color="#1F3864", lw=2.5)
ax[0].set_title("Vazão (trens/dia): trava no porto", fontweight="bold")
ax[1].plot(Ns, [fila_modelo(n) for n in Ns], color="#E4572E", lw=2.5)
ax[1].scatter([N_frota], [df[col_fila].mean()], color="black", zorder=5, label="fila observada hoje")
ax[1].set_title(f"Fila no porto (h): +{S_med:.1f} h por trem extra", fontweight="bold")
ax[1].legend(frameon=False, loc="upper left")
for a_ in ax:
    a_.axvline(N_frota, color="gray", ls=":")
    a_.set_xlabel("Trens na frota")
ax[0].set_ylabel("trens/dia"); ax[1].set_ylabel("horas")
ax[0].text(N_frota + 0.1, ax[0].get_ylim()[0] + 0.05, "frota atual", color="gray")
plt.tight_layout(); plt.savefig("fig1_frota_vs_fila.png", dpi=200); plt.close()

# Gráfico 2: onde cada incidente consome capacidade (por etapa do ciclo)
inc = df_impacto[df_impacto["horas_ativo_perdidas"] > 10].sort_values("horas_ativo_perdidas")
rotulo = inc["data"].str[8:] + "/" + inc["data"].str[5:7] + " " + inc["categoria"]
cores = ["#1F3864", "#E4572E", "#8A8F98", "#2A9D8F"]
plt.figure(figsize=(9, 4))
# Horas por etapa: só as etapas que passaram do normal (as que ficaram abaixo não entram na barra).
etapas_pos = np.column_stack([(inc["delta_" + NOME[e]].clip(lower=0) * 6).values for e in ETAPAS])
etapas_pos = etapas_pos / etapas_pos.sum(axis=1, keepdims=True) * inc["horas_ativo_perdidas"].values[:, None]
esq = np.zeros(len(inc))
for i, (e, c) in enumerate(zip(ETAPAS, cores)):
    plt.barh(rotulo, etapas_pos[:, i], left=esq, color=c, label=NOME[e]); esq += etapas_pos[:, i]
plt.grid(axis="y", visible=False); plt.xlabel("Horas de ativo perdidas no dia"); plt.legend(frameon=False, loc="lower right")
plt.title("Onde cada incidente consome capacidade", fontweight="bold")
plt.tight_layout(); plt.savefig("fig2_perda_por_evento.png", dpi=200); plt.close()

# Gráfico 3: capacidade da frota por percentil do ciclo (variabilidade e risco: não só a média)
plt.figure(figsize=(8, 4.2))
barras = plt.bar(list(cap_trens_dia.keys()), list(cap_trens_dia.values()),
                 color=["#1F3864", "#1F3864", "#1F3864", "#1F3864"])   # P90 em destaque
plt.bar_label(barras, fmt="%.2f", fontsize=11)
plt.grid(axis="x", visible=False); plt.ylabel("Trens por dia"); plt.ylim(0, 7)
plt.title("Capacidade da frota atual por percentil do ciclo", fontweight="bold")
plt.tight_layout(); plt.savefig("fig3_capacidade_percentil.png", dpi=200); plt.close()

# Gráfico 4: capacidade da frota toneladas por percentil do ciclo (variabilidade e risco: não só a média)
plt.figure(figsize=(8, 4.2))
barras = plt.bar(list(cap_ton_dia.keys()), list(cap_ton_dia.values()),
                 color=["#1F3864", "#1F3864", "#1F3864", "#1F3864"])   # P90 em destaque
plt.bar_label(barras, fmt="%.2f", fontsize=11)
plt.grid(axis="x", visible=False); plt.ylabel("Ton por dia"); plt.ylim(0, 100000)
plt.title("Capacidade da frota atual por percentil do ciclo", fontweight="bold")
plt.tight_layout(); plt.savefig("fig4_capacidade_percentil_ton.png", dpi=200); plt.close()


# Gráfico 5: Pareto das horas-trem perdidas por causa (qual causa pesa mais e o acumulado)
from matplotlib.patches import Patch

pareto = (df_impacto[df_impacto["horas_ativo_perdidas"] > 0]       # só eventos com perda
          .groupby("categoria")["horas_ativo_perdidas"].sum()
          .sort_values(ascending=False))                           # maior para o menor
acumulado = pareto.cumsum() / pareto.sum() * 100                   # % acumulado
nome_curto = {"Clima (Serra)": "Clima na Serra", "Restrição do porto": "Restrição do porto",
              "Via permanente": "Via permanente", "Equipamento do terminal": "Equipamento do terminal"}
cor_causa = {"Clima (Serra)": "#1F3864", "Via permanente": "#1F3864",          # trânsito
             "Restrição do porto": "#E4572E", "Equipamento do terminal": "#E4572E"}  # fila no porto
rotulos = [nome_curto[c] for c in pareto.index]

fig, ax = plt.subplots(figsize=(9, 4.6))
barras = ax.bar(rotulos, pareto.values, color=[cor_causa[c] for c in pareto.index])
ax.bar_label(barras, labels=[f"{v:.0f} h\n({v / pareto.sum() * 100:.0f}%)" for v in pareto.values],
             label_type="center", color="white", fontsize=11, fontweight="bold")   # rótulo dentro da barra
ax.set_ylabel("Horas-trem perdidas"); ax.set_ylim(0, pareto.sum() * 1.1)   # 100% acumulado = soma total das horas
ax.grid(axis="x", visible=False)
ax2 = ax.twinx()                                                    # eixo da direita: % acumulado
ax2.plot(rotulos, acumulado.values, color="#8A8F98", marker="o", lw=2)
ax2.set_ylim(0, 110); ax2.set_ylabel("% acumulado"); ax2.grid(False)   # mesma escala do eixo da esquerda
for i, v in enumerate(acumulado.values):
    ax2.annotate(f"{v:.0f}%", (i, v), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=9, color="#5B6270")
ax.legend(handles=[Patch(color="#1F3864", label="Atinge o trânsito"), Patch(color="#E4572E", label="Atinge a fila no porto")],
          frameon=False, loc="upper right", bbox_to_anchor=(1.0, 0.72))
plt.title("Pareto: horas-trem perdidas por causa", fontweight="bold")
plt.tight_layout(); plt.savefig("fig5_pareto_horas.png", dpi=200); plt.close()


def limpar_json(o):
    """JSON não aceita NaN: troca por null e converte tipos do numpy."""
    if isinstance(o, dict):
        return {k: limpar_json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [limpar_json(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else round(float(o), 4)
    if isinstance(o, np.integer):
        return int(o)
    return o


resultados = {
    "qualidade_dados": qualidade,
    "eventos_logs": df_log.assign(data=df_log["data"].dt.strftime("%Y-%m-%d")).to_dict("records"),
    "impacto_por_evento": df_impacto.to_dict("records"),
    "horas_ativo_perdidas_incidentes": round(horas_total, 0),
    "spearman_fila_ciclo": round(float(rho_fc), 2),
    "teoria_das_filas": {"lambda_trens_dia": round(lam, 2), "mu_trens_dia": round(mu, 2), "rho": round(rho, 3),
                         "ciclo_sem_fila_h": round(D, 1), "frota_que_satura_porto": round(N_sat, 1),
                         "fila_prevista_h": round(fila_modelo(N_frota), 1), "fila_observada_h": round(float(df[col_fila].mean()), 1)},
    "capacidade_real": {"frota_em_circulacao": round(N_frota, 1), "ciclo_percentis_h": {k: round(v, 1) for k, v in percentis.items()},
                        "capacidade_trens_dia": cap_trens_dia, "capacidade_ton_dia": cap_ton_dia},
    "resposta_hipotese_comercial": {
        "teto_ganho_vazao_com_mais_trens_pct": round(teto_ganho_pct, 1),
        "frota_vs_vazao_e_fila": tabela_frota,
        "fila_extra_por_trem_h": round(S_med, 1),
        "conclusao": "Mais trens elevam a vazão em no máximo o teto acima e aumentam a fila: o gargalo é a descarga no porto."},
    "ganho_opex_descarga_mais_rapida": df_ganho.to_dict("records"),
    "premissas_e_limites": [
        "μ assume 1 posição de descarga com o tempo médio observado; a base não informa posições nem capacidade do porto.",
        "O ganho OPEX depende de uma premissa (descarga +p%) a validar com o porto; mostrada de 5% a 20%.",
        "Modelo de circuito fechado (leis de Little e do gargalo): ignora variabilidade, por isso é um teto; a fila prevista bate com a observada.",
        "Baseline única: o ciclo médio é maior em julho; a comparação pode subestimar eventos de junho.",
        "56% das linhas repetem o vetor de tempos; os logs falam em 12 trens/dia e 450 t/h, a base mostra 6/dia e teto de 12.100 t.",
        "Toneladas por ano são extrapolação do período de 61 dias, sem custos (R$)."],
}
with open("results.json", "w", encoding="utf-8") as fj:
    json.dump(limpar_json(resultados), fj, indent=2, ensure_ascii=False, default=str, allow_nan=False)
print("\nConcluído. Artefatos: fig1_frota_vs_fila.png, fig2_perda_por_evento.png, fig3_capacidade_percentil.png,fig4_capacidade_percentil_ton.png, fig5_pareto_horas.png, results.json")
