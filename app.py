import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------
# CONFIGURACIÓN DE LA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Motor de Secuenciación y Reglas de Despacho",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚙️ Motor de Secuenciación y Reglas de Despacho")
st.markdown("---")

# ---------------------------------------------------------
# PANEL 1: DATOS DE ENTRADA (SIDEBAR)
# ---------------------------------------------------------
st.sidebar.header("PANEL 1 — Datos de Entrada")

# Opción para cargar archivo
uploaded_file = st.sidebar.file_uploader("Cargar desde Excel o CSV", type=["xlsx", "csv"])

# Datos por defecto (mismos datos de tu ejercicio)
datos_defecto = pd.DataFrame({
    'Trabajo': ['A', 'B', 'C', 'D', 'E', 'F'],
    'Llegada': [0, 0, 0, 0, 0, 0],
    'Proceso': [5, 7, 3, 12, 9, 11],
    'Deadline': [10, 9, 6, 15, 15, 14]
})

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df_input = pd.read_csv(uploaded_file)
        else:
            df_input = pd.read_excel(uploaded_file)
        st.sidebar.success("Archivo cargado correctamente.")
    except Exception as e:
        st.sidebar.error(f"Error al leer el archivo: {e}")
        df_input = datos_defecto
else:
    df_input = datos_defecto

st.sidebar.subheader("Tabla editable de trabajos:")
df_trabajos = st.sidebar.data_editor(df_input, num_rows="dynamic", use_container_width=True)

# ---------------------------------------------------------
# MOTOR DE CÁLCULO
# ---------------------------------------------------------
def simular_secuencia(df_seq):
    """Calcula los tiempos de inicio, fin, tardanza y trabajos tardíos para una secuencia dada."""
    df = df_seq.copy().reset_index(drop=True)
    tiempo_actual = 0
    inicios, fines, tardanzas, tardios = [], [], [], []

    for _, row in df.iterrows():
        inicio = max(tiempo_actual, row['Llegada'])
        fin = inicio + row['Proceso']
        tiempo_actual = fin
        
        tardanza = max(0, fin - row['Deadline'])
        es_tardio = 1 if tardanza > 0 else 0

        inicios.append(inicio)
        fines.append(fin)
        tardanzas.append(tardanza)
        tardios.append(es_tardio)

    df['Tiempo de Inicio'] = inicios
    df['Tiempo de Terminacion'] = fines
    df['Tardanza'] = tardanzas
    df['Trabajo Tardio'] = tardios
    return df

def ejecutar_reglas_despacho(df):
    """Aplica las reglas de despacho y calcula los indicadores globales."""
    df_base = df.copy()
    if 'Llegada' not in df_base.columns:
        df_base['Llegada'] = 0

    # Definición de Secuencias según Reglas
    reglas_dict = {
        'FIFO': df_base.copy(),
        'LIFO': df_base.iloc[::-1].copy(),
        'SPT': df_base.sort_values(by=['Proceso', 'Deadline'], ascending=[True, True]),
        'LPT': df_base.sort_values(by=['Proceso', 'Deadline'], ascending=[False, True]),
        'EDD': df_base.sort_values(by=['Deadline', 'Proceso'], ascending=[True, True]),
        'MS': df_base.assign(Slack=df_base['Deadline'] - df_base['Proceso']).sort_values(by='Slack', ascending=True),
        'CR': df_base.assign(CR=df_base['Deadline'] / np.where(df_base['Proceso']==0, 1e-5, df_base['Proceso'])).sort_values(by='CR', ascending=True)
    }

    resultados_kpis = {}
    tablas_secuencias = {}

    for nombre_regla, df_ordenado in reglas_dict.items():
        df_sim = simular_secuencia(df_ordenado)
        tablas_secuencias[nombre_regla] = df_sim

        makespan = df_sim['Tiempo de Terminacion'].max() if not df_sim.empty else 0
        ct = df_sim['Tiempo de Terminacion'].sum()
        tmax = df_sim['Tardanza'].max()
        tt = df_sim['Trabajo Tardio'].sum()
        ttotal = df_sim['Tardanza'].sum()
        wip = round(ct / makespan, 2) if makespan > 0 else 0

        resultados_kpis[nombre_regla] = {
            'MAKESPAN': int(makespan),
            'TMAX': int(tmax),
            'TT': int(tt),
            'CT': int(ct),
            'TTOTAL': int(ttotal),
            'WIP': wip
        }

    df_indicadores = pd.DataFrame(resultados_kpis)
    df_indicadores.index.name = 'TABLA DE INDICADORES'
    return df_indicadores, tablas_secuencias

# Ejecución del motor
df_indicadores, tablas_secuencias = ejecutar_reglas_despacho(df_trabajos)

# ---------------------------------------------------------
# TABLA COMPARATIVA GENERAL (ESTRUCTURA DE TU EXCEL)
# ---------------------------------------------------------
st.subheader("📊 Tabla de Indicadores por Regla de Despacho")
st.dataframe(df_indicadores, use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------
# PANEL 2: INSPECCIÓN DETALLADA Y DASHBOARD
# ---------------------------------------------------------
col_izq, col_der = st.columns([1, 1])

with col_izq:
    st.subheader("🔍 Inspección por Regla")
    
    # Lógica de recomendación (Regla con menor Tardanza Total y CT)
    regla_recomendada = df_indicadores.T.sort_values(by=['TTOTAL', 'CT', 'TMAX']).index[0]
    st.success(f"🏆 **Regla Recomendada Automáticamente:** `{regla_recomendada}`")

    regla_seleccionada = st.selectbox("Seleccionar Regla para Inspeccionar:", list(df_indicadores.columns), index=0)

    # Tarjetas de Indicadores en 2 filas
    kpis = df_indicadores[regla_seleccionada]
    
    m1, m2, m3 = st.columns(3)
    m1.metric("MAKESPAN", kpis['MAKESPAN'])
    m2.metric("TMAX", kpis['TMAX'])
    m3.metric("TT", kpis['TT'])

    m4, m5, m6 = st.columns(3)
    m4.metric("CT (Suma Ci)", kpis['CT'])
    m5.metric("TTOTAL", kpis['TTOTAL'])
    m6.metric("WIP", f"{kpis['WIP']:.2f}")

    st.info("ℹ️ **Fórmula usada para WIP:** $\\text{WIP} = \\frac{\\sum C_i}{C_{\\max}}$")

    # Tabla de la secuencia seleccionada
    st.markdown(f"**Secuencia de Trabajos ({regla_seleccionada}):**")
    df_sec_sel = tablas_secuencias[regla_seleccionada][['Trabajo', 'Tiempo de Inicio', 'Tiempo de Terminacion', 'Proceso', 'Tardanza', 'Trabajo Tardio']]
    st.dataframe(df_sec_sel, use_container_width=True, hide_index=True)

with col_der:
    st.subheader("📈 Análisis Gráfico Radial (Araña)")

    # Normalización de indicadores (100 = Mejor Desempeño)
    df_norm = df_indicadores.astype(float).copy()
    
    # Para todos los indicadores, menor valor es mejor
    for idx in df_norm.index:
        min_val = df_norm.loc[idx].min()
        max_val = df_norm.loc[idx].max()
        if max_val == min_val:
            df_norm.loc[idx] = 100.0
        else:
            df_norm.loc[idx] = 100 * (1 - (df_norm.loc[idx] - min_val) / (max_val - min_val + 1e-5))

    categories = list(df_norm.index)
    
    fig_radar = go.Figure()

    # Agregar la regla recomendada y la seleccionada al gráfico radial
    for regla in set([regla_seleccionada, regla_recomendada, 'FIFO', 'SPT']):
        values = df_norm[regla].tolist()
        values.append(values[0]) # Cerrar el polígono
        
        fig_radar.add_trace(go.Scatterpolar(
            r=values,
            theta=categories + [categories[0]],
            fill='toself' if regla == regla_seleccionada else None,
            name=regla,
            opacity=0.6 if regla == regla_seleccionada else 0.3
        ))

    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100])
        ),
        title=dict(text="Desempeño Normalizado (100 = Mejor Desempeño)", x=0.5),
        showlegend=True,
        height=450
    )

    st.plotly_chart(fig_radar, use_container_width=True)

# ---------------------------------------------------------
# GRAFICA DE GANTT
# ---------------------------------------------------------
st.markdown("---")
st.subheader(f"📅 Diagrama de Gantt — Regla {regla_seleccionada}")

df_gantt = tablas_secuencias[regla_seleccionada].copy()
df_gantt['Inicio_Str'] = df_gantt['Tiempo de Inicio']
df_gantt['Duracion'] = df_gantt['Proceso']

fig_gantt = px.timeline(
    df_gantt,
    x_start="Tiempo de Inicio",
    x_end="Tiempo de Terminacion",
    y="Trabajo",
    color="Trabajo",
    text="Trabajo",
    title=f"Programación de Trabajos en Máquina ({regla_seleccionada})"
)

fig_gantt.update_yaxes(autorange="reversed")
fig_gantt.update_layout(
    xaxis_title="Tiempo (Unidades de tiempo)",
    yaxis_title="Trabajo",
    height=350,
    showlegend=False
)

st.plotly_chart(fig_gantt, use_container_width=True)
