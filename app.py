import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ---------------------------------------------------------
st.set_page_config(page_title="Motor de Secuenciación", layout="wide")
st.title("⚙️ Motor de Secuenciación y Reglas de Despacho")
st.markdown("---")

# ---------------------------------------------------------
# PANEL 1: DATOS DE ENTRADA (SIDEBAR)
# ---------------------------------------------------------
st.sidebar.header("PANEL 1 — Datos de Entrada")

st.sidebar.subheader("1.1 Tabla de Trabajos")
uploaded_file = st.sidebar.file_uploader("Cargar desde Excel o CSV", type=["xlsx", "csv"])

datos_defecto = pd.DataFrame({
    'Trabajo': ['A', 'B', 'C', 'D', 'E', 'F'],
    'Llegada': [0, 0, 0, 0, 0, 0],
    'Proceso': [5, 7, 3, 12, 9, 11],
    'Deadline': [10, 9, 6, 15, 15, 14]
})

if uploaded_file is not None:
    try:
        df_input = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    except Exception:
        df_input = datos_defecto
else:
    df_input = datos_defecto

df_trabajos = st.sidebar.data_editor(df_input, num_rows="dynamic", use_container_width=True)

# Trabajos activos
lista_trabajos = df_trabajos['Trabajo'].astype(str).tolist()

st.sidebar.subheader("1.2 Matriz de Alistamiento ($S_{ij}$)")
st.sidebar.caption("Filas: Trabajo Saliente ($i$) | Columnas: Trabajo Entrante ($j$)")

# Matriz con los valores exactos de tu imagen
matriz_imagen = pd.DataFrame(
    data=[
        [0, 2, 3, 1, 4, 2],
        [1, 0, 1, 2, 3, 4],
        [1, 2, 0, 2, 3, 3],
        [3, 4, 5, 0, 2, 4],
        [2, 1, 2, 3, 0, 1],
        [1, 3, 4, 5, 6, 0]
    ],
    index=['A', 'B', 'C', 'D', 'E', 'F'],
    columns=['A', 'B', 'C', 'D', 'E', 'F']
)

# Reindexado según los trabajos configurados
df_alistamiento = matriz_imagen.reindex(index=lista_trabajos, columns=lista_trabajos, fill_value=0)
df_alistamiento = st.sidebar.data_editor(df_alistamiento, use_container_width=True)

# ---------------------------------------------------------
# MOTOR DE CÁLCULO
# ---------------------------------------------------------
def simular_secuencia(df_seq, matrix_s):
    df = df_seq.copy().reset_index(drop=True)
    tiempo_actual = 0
    tiempos_alist, inicios_proc, fines_proc, tardanzas, tardios, transiciones = [], [], [], [], [], []
    
    prev_job = None
    for _, row in df.iterrows():
        curr_job = str(row['Trabajo'])
        
        if prev_job is not None and prev_job in matrix_s.index and curr_job in matrix_s.columns:
            s_time = float(matrix_s.loc[prev_job, curr_job])
            trans_str = f"{prev_job} → {curr_job}"
        else:
            s_time = 0.0
            trans_str = "Inicio Linea"
            
        inicio_alist = max(tiempo_actual, row['Llegada'])
        inicio_p = inicio_alist + s_time
        fin_p = inicio_p + row['Proceso']
        
        tiempo_actual = fin_p
        tardanza = max(0, fin_p - row['Deadline'])
        
        transiciones.append(trans_str)
        tiempos_alist.append(s_time)
        inicios_proc.append(inicio_p)
        fines_proc.append(fin_p)
        tardanzas.append(tardanza)
        tardios.append(1 if tardanza > 0 else 0)
        
        prev_job = curr_job
        
    df['Transicion'] = transiciones
    df['Alistamiento'] = tiempos_alist
    df['Tiempo de Inicio'] = inicios_proc
    df['Tiempo de Terminacion'] = fines_proc
    df['Tardanza'] = tardanzas
    df['Trabajo Tardio'] = tardios
    return df

def ejecutar_reglas_despacho(df, matrix_s):
    df_base = df.copy()
    if 'Llegada' not in df_base.columns: 
        df_base['Llegada'] = 0
        
    reglas = {
        'FIFO': df_base.copy(),
        'LIFO': df_base.iloc[::-1].copy(),
        'SPT': df_base.sort_values(by=['Proceso', 'Deadline']),
        'LPT': df_base.sort_values(by=['Proceso', 'Deadline'], ascending=[False, True]),
        'EDD': df_base.sort_values(by=['Deadline', 'Proceso']),
        'MS': df_base.assign(Slack=df_base['Deadline'] - df_base['Proceso']).sort_values(by='Slack'),
        'CR': df_base.assign(CR=df_base['Deadline'] / np.where(df_base['Proceso']==0, 1e-5, df_base['Proceso'])).sort_values(by='CR')
    }
    
    kpis, secuencias = {}, {}
    n_trabajos = len(df_base)
    
    for r, df_ord in reglas.items():
        df_sim = simular_secuencia(df_ord, matrix_s)
        secuencias[r] = df_sim
        mk = df_sim['Tiempo de Terminacion'].max() if not df_sim.empty else 0
        ct = df_sim['Tiempo de Terminacion'].sum()
        cprom = ct / n_trabajos if n_trabajos > 0 else 0
        
        kpis[r] = {
            'MAKESPAN': int(mk),
            'TMAX': int(df_sim['Tardanza'].max()),
            'TTOTAL': int(df_sim['Tardanza'].sum()),
            'TT': int(df_sim['Trabajo Tardio'].sum()),
            'CT': int(ct),
            'C_PROM': round(cprom, 2),
            'WIP': round(ct / mk, 2) if mk > 0 else 0
        }
        
    return pd.DataFrame(kpis), secuencias

df_indicadores, tablas_secuencias = ejecutar_reglas_despacho(df_trabajos, df_alistamiento)

# ---------------------------------------------------------
# PANEL 2: RESUMEN Y RECOMENDACIÓN
# ---------------------------------------------------------
st.header("PANEL 2 — Resumen y Recomendación")
regla_recomendada = df_indicadores.T.sort_values(by=['TTOTAL', 'CT', 'TMAX']).index[0]
st.success(f"🏆 **Regla Recomendada Automáticamente:** `{regla_recomendada}`")

regla_sel = st.selectbox("Seleccionar Regla para Inspeccionar en Tarjetas, Matriz y Gantt:", list(df_indicadores.columns), index=0)

k = df_indicadores[regla_sel]
m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
m1.metric("MAKESPAN", k['MAKESPAN'])
m2.metric("TMAX", k['TMAX'])
m3.metric("TTOTAL", k['TTOTAL'])
m4.metric("TT", k['TT'])
m5.metric("CT", k['CT'])
m6.metric("C PROM", k['C_PROM'])
m7.metric("WIP", f"{k['WIP']:.2f}")

st.markdown("---")

# ---------------------------------------------------------
# PANEL 3: COMPARACIÓN Y GRÁFICO RADIAL INTERACTIVO
# ---------------------------------------------------------
st.header("PANEL 3 — Comparación")

st.subheader("📊 Tabla Comparativa de Indicadores")
st.dataframe(df_indicadores, use_container_width=True)

st.subheader("🕸️ Gráfico Radial / Polar de Desempeño Interactivo")

ejes_config = [
    ('MAKESPAN', 'Makespan'),
    ('TMAX', 'Tmax'),
    ('TTOTAL', 'Tardanza Total'),
    ('TT', 'Trabajos tardíos'),
    ('CT', 'Tiempo Total de Terminación'),
    ('C_PROM', 'C promedio'),
    ('WIP', 'WIP')
]

df_scores = pd.DataFrame(index=[e[1] for e in ejes_config], columns=df_indicadores.columns)
df_orig = pd.DataFrame(index=[e[1] for e in ejes_config], columns=df_indicadores.columns)

for id_kpi, nombre_eje in ejes_config:
    valores_orig = df_indicadores.loc[id_kpi].astype(float)
    df_orig.loc[nombre_eje] = valores_orig
    val_min = valores_orig.min()
    val_max = valores_orig.max()
    
    if val_max == val_min:
        df_scores.loc[nombre_eje] = 100.0
    else:
        df_scores.loc[nombre_eje] = 100.0 * (val_max - valores_orig) / (val_max - val_min)

reglas_seleccionadas = st.multiselect(
    "Seleccionar reglas para comparar visualmente (Activar/Desactivar):",
    options=list(df_indicadores.columns),
    default=list(df_indicadores.columns)
)

categories = [e[1] for e in ejes_config]
categories_closed = categories + [categories[0]]

fig_radar = go.Figure()

for r in reglas_seleccionadas:
    r_scores = df_scores[r].tolist()
    r_scores_closed = r_scores + [r_scores[0]]
    
    r_orig = df_orig[r].tolist()
    r_orig_closed = r_orig + [r_orig[0]]
    
    custom_data = np.stack((r_orig_closed, r_scores_closed), axis=-1)
    
    fig_radar.add_trace(go.Scatterpolar(
        r=r_scores_closed,
        theta=categories_closed,
        name=r,
        customdata=custom_data,
        fill='toself' if r == regla_sel else None,
        opacity=0.8 if r == regla_sel else 0.4,
        hovertemplate=(
            f"<b>Regla:</b> {r}<br>"
            "<b>Indicador:</b> %{theta}<br>"
            "<b>Valor Original:</b> %{customdata[0]}<br>"
            "<b>Score Desempeño:</b> %{customdata[1]:.1f} / 100"
            "<extra></extra>"
        )
    ))

fig_radar.update_layout(
    polar=dict(
        radialaxis=dict(
            visible=True,
            range=[0, 100],
            showline=True,
            gridcolor='lightgray'
        )
    ),
    height=520,
    showlegend=True,
    legend=dict(
        title=dict(text="Leyenda de Reglas (Clic para ocultar/aislar):"),
        orientation="h",
        yanchor="bottom",
        y=-0.25,
        xanchor="center",
        x=0.5
    ),
    margin=dict(l=60, r=60, t=30, b=100)
)

st.plotly_chart(fig_radar, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------
# PANEL 4: SECUENCIA, ALISTAMIENTOS Y GANTT INTERACTIVO
# ---------------------------------------------------------
st.header("PANEL 4 — Secuencia y Diagrama de Gantt")

# 1. Visualización de la Matriz General con Estilo de Imagen
st.subheader("🛠️ Matriz de Alistamiento General ($S_{ij}$)")

# Función de estilizado para colorear la diagonal de azul igual que la imagen
def estilizar_matriz(df):
    def highlight_diag(data):
        attr = 'background-color: #38bdf8; color: transparent;'
        m = pd.DataFrame('', index=data.index, columns=data.columns)
        for i in range(min(len(data.index), len(data.columns))):
            m.iloc[i, i] = attr
        return m
    return df.style.apply(highlight_diag, axis=None)

st.dataframe(estilizar_matriz(df_alistamiento), use_container_width=True)

# 2. Secuencia Detallada con Tiempos de Alistamiento
st.subheader(f"📋 Secuencia Detallada y Cambios de Preparación ({regla_sel})")
st.dataframe(
    tablas_secuencias[regla_sel][['Trabajo', 'Transicion', 'Alistamiento', 'Tiempo de Inicio', 'Tiempo de Terminacion', 'Proceso', 'Tardanza', 'Trabajo Tardio']], 
    use_container_width=True, 
    hide_index=True
)

# 3. Diagrama de Gantt Interactivo
st.subheader(f"📅 Diagrama de Gantt Interactivo ({regla_sel})")
df_gantt = tablas_secuencias[regla_sel].copy()

fig_gantt = go.Figure()

for _, row in df_gantt.iterrows():
    estado = "Tardío" if row["Tardanza"] > 0 else "A tiempo"
    color_proceso = "#ef4444" if row["Tardanza"] > 0 else "#22c55e"
    
    # Bloque Gris de Alistamiento
    if row['Alistamiento'] > 0:
        inicio_alist = row['Tiempo de Inicio'] - row['Alistamiento']
        hover_alist = (
            f"<b>Trabajo:</b> {row['Trabajo']} (Alistamiento)<br>"
            f"<b>Transición:</b> {row['Transicion']}<br>"
            f"<b>Inicio Alistamiento:</b> {inicio_alist}<br>"
            f"<b>Fin Alistamiento:</b> {row['Tiempo de Inicio']}<br>"
            f"<b>Tiempo Alistamiento:</b> {row['Alistamiento']}"
        )
        fig_gantt.add_trace(go.Bar(
            x=[row["Alistamiento"]],
            y=[row["Trabajo"]],
            base=[inicio_alist],
            orientation='h',
            marker_color='#9ca3af',
            name=f"Alistamiento {row['Trabajo']}",
            hovertemplate=hover_alist + "<extra></extra>"
        ))

    # Bloque Color (Verde/Rojo) de Proceso
    hovertxt = (
        f"<b>Trabajo:</b> {row['Trabajo']}<br>"
        f"<b>Regla:</b> {regla_sel}<br>"
        f"<b>Transición:</b> {row['Transicion']}<br>"
        f"<b>Tiempo Alistamiento:</b> {row['Alistamiento']}<br>"
        f"<b>Inicio Proceso:</b> {row['Tiempo de Inicio']}<br>"
        f"<b>Fin Proceso:</b> {row['Tiempo de Terminacion']}<br>"
        f"<b>Tiempo Proceso:</b> {row['Proceso']}<br>"
        f"<b>Fecha Entrega:</b> {row['Deadline']}<br>"
        f"<b>Tardanza:</b> {row['Tardanza']}<br>"
        f"<b>Estado:</b> {estado}"
    )
    
    fig_gantt.add_trace(go.Bar(
        x=[row["Proceso"]],
        y=[row["Trabajo"]],
        base=[row["Tiempo de Inicio"]],
        orientation='h',
        marker_color=color_proceso,
        name=str(row["Trabajo"]),
        hovertemplate=hovertxt + "<extra></extra>"
    ))

fig_gantt.update_yaxes(autorange="reversed")
fig_gantt.update_layout(
    title=f"Programación de Trabajos ({regla_sel}) — Gris: Alistamiento | Verde: A tiempo | Rojo: Tardío",
    xaxis_title="Tiempo (Unidades)",
    yaxis_title="Trabajo",
    height=420,
    showlegend=False
)

st.plotly_chart(fig_gantt, use_container_width=True)
