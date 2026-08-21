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

# ---------------------------------------------------------
# MOTOR DE CÁLCULO
# ---------------------------------------------------------
def simular_secuencia(df_seq):
    df = df_seq.copy().reset_index(drop=True)
    tiempo_actual, inicios, fines, tardanzas, tardios = 0, [], [], [], []
    for _, row in df.iterrows():
        inicio = max(tiempo_actual, row['Llegada'])
        fin = inicio + row['Proceso']
        tiempo_actual = fin
        tardanza = max(0, fin - row['Deadline'])
        inicios.append(inicio)
        fines.append(fin)
        tardanzas.append(tardanza)
        tardios.append(1 if tardanza > 0 else 0)
    df['Tiempo de Inicio'] = inicios
    df['Tiempo de Terminacion'] = fines
    df['Tardanza'] = tardanzas
    df['Trabajo Tardio'] = tardios
    return df

def ejecutar_reglas_despacho(df):
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
    for r, df_ord in reglas.items():
        df_sim = simular_secuencia(df_ord)
        secuencias[r] = df_sim
        mk = df_sim['Tiempo de Terminacion'].max() if not df_sim.empty else 0
        ct = df_sim['Tiempo de Terminacion'].sum()
        kpis[r] = {
            'MAKESPAN': int(mk),
            'TMAX': int(df_sim['Tardanza'].max()),
            'TT': int(df_sim['Trabajo Tardio'].sum()),
            'CT': int(ct),
            'TTOTAL': int(df_sim['Tardanza'].sum()),
            'WIP': round(ct / mk, 2) if mk > 0 else 0
        }
    return pd.DataFrame(kpis), secuencias

df_indicadores, tablas_secuencias = ejecutar_reglas_despacho(df_trabajos)

# ---------------------------------------------------------
# PANEL 2 Y PANEL 3 (DASHBOARD)
# ---------------------------------------------------------
col1, col2 = st.columns([1, 1.1])

with col1:
    st.header("PANEL 2 — Resumen y Recomendación")
    regla_recomendada = df_indicadores.T.sort_values(by=['TTOTAL', 'CT', 'TMAX']).index[0]
    st.success(f"🏆 **Regla Recomendada Automáticamente:** `{regla_recomendada}`")
    
    # Asignación de la variable elegida
    regla_sel = st.selectbox("Seleccionar Regla para Inspeccionar:", list(df_indicadores.columns), index=0)

    k = df_indicadores[regla_sel]
    m1, m2, m3 = st.columns(3)
    m1.metric("MAKESPAN", k['MAKESPAN'])
    m2.metric("TMAX", k['TMAX'])
    m3.metric("TT", k['TT'])

    m4, m5, m6 = st.columns(3)
    m4.metric("CT (Suma Ci)", k['CT'])
    m5.metric("TTOTAL", k['TTOTAL'])
    m6.metric("WIP", f"{k['WIP']:.2f}")

with col2:
    st.header("PANEL 3 — Comparación")
    tab_tabla, tab_radial = st.tabs(["📊 Tabla Comparativa", "🕸️ Gráfico Radial"])
    
    with tab_tabla:
        st.dataframe(df_indicadores, use_container_width=True)
        
    with tab_radial:
        df_norm = df_indicadores.astype(float).copy()
        for idx in df_norm.index:
            mn, mx = df_norm.loc[idx].min(), df_norm.loc[idx].max()
            df_norm.loc[idx] = 100.0 if mx == mn else 100 * (1 - (df_norm.loc[idx] - mn) / (mx - mn + 1e-5))
        
        fig_radar = go.Figure()
        for r in set([regla_sel, regla_recomendada, 'FIFO', 'SPT']):
            v = df_norm[r].tolist()
            fig_radar.add_trace(go.Scatterpolar(r=v+[v[0]], theta=list(df_norm.index)+[df_norm.index[0]], name=r, fill='toself' if r==regla_sel else None))
        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=350, showlegend=True)
        st.plotly_chart(fig_radar, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------
# PANEL 4: SECUENCIA Y GANTT INTERACTIVO
# ---------------------------------------------------------
st.header("PANEL 4 — Secuencia y Diagrama de Gantt")

st.subheader(f"📋 Secuencia Detallada ({regla_sel})")
st.dataframe(
    tablas_secuencias[regla_sel][['Trabajo', 'Tiempo de Inicio', 'Tiempo de Terminacion', 'Proceso', 'Tardanza', 'Trabajo Tardio']], 
    use_container_width=True, 
    hide_index=True
)

st.subheader(f"📅 Diagrama de Gantt ({regla_sel})")
df_gantt = tablas_secuencias[regla_sel].copy()

fig_gantt = go.Figure()

for _, row in df_gantt.iterrows():
    estado = "Tardío" if row["Tardanza"] > 0 else "A tiempo"
    color = "#ef4444" if row["Tardanza"] > 0 else "#22c55e"  # Rojo si es tardío, verde si es a tiempo
    
    hovertxt = (
        f"<b>Trabajo:</b> {row['Trabajo']}<br>"
        f"<b>Regla:</b> {regla_sel}<br>"
        f"<b>Inicio:</b> {row['Tiempo de Inicio']}<br>"
        f"<b>Fin:</b> {row['Tiempo de Terminacion']}<br>"
        f"<b>Tiempo de proceso:</b> {row['Proceso']}<br>"
        f"<b>Fecha de entrega:</b> {row['Deadline']}<br>"
        f"<b>Tardanza:</b> {row['Tardanza']}<br>"
        f"<b>Estado:</b> {estado}"
    )
    
    fig_gantt.add_trace(go.Bar(
        x=[row["Proceso"]],
        y=[row["Trabajo"]],
        base=[row["Tiempo de Inicio"]],
        orientation='h',
        marker_color=color,
        name=str(row["Trabajo"]),
        hovertemplate=hovertxt + "<extra></extra>"
    ))

fig_gantt.update_yaxes(autorange="reversed")
fig_gantt.update_layout(
    title=f"Programación de Trabajos ({regla_sel}) — Verde: A tiempo | Rojo: Tardío",
    xaxis_title="Tiempo (Unidades)",
    yaxis_title="Trabajo",
    height=380,
    showlegend=False
)

st.plotly_chart(fig_gantt, use_container_width=True)
