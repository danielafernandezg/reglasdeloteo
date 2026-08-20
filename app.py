import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# Configuración de la página
st.set_page_config(page_title="Sistema de Secuenciación y Reglas de Despacho", layout="wide")
st.title("SISTEMA INTERACTIVO DE SECUENCIACIÓN Y REGLAS DE DESPACHO")

# ==========================================
# 1. MOTOR DE SECUENCIACIÓN Y REGLAS (LÓGICA DINÁMICA)
# ==========================================
def calcular_secuencia(df, regla):
    # Convertimos los datos a una lista de diccionarios para no usar .loc ni iteraciones complejas
    trabajos = df.to_dict('records')
    for idx, t in enumerate(trabajos):
        t['Estado'] = 'Pendiente'
        t['Orden_Original'] = idx
        
    tiempo_actual = 0
    secuencia = []
    
    while any(t['Estado'] == 'Pendiente' for t in trabajos):
        pendientes = [t for t in trabajos if t['Estado'] == 'Pendiente']
        disponibles = [t for t in pendientes if t['Llegada'] <= tiempo_actual]
        
        # Si la máquina está libre pero no han llegado trabajos, se avanza el tiempo
        if not disponibles:
            tiempo_actual = min(t['Llegada'] for t in pendientes)
            disponibles = [t for t in pendientes if t['Llegada'] <= tiempo_actual]
            
        # --- Aplicación de Reglas de Despacho y Criterios de Desempate ---
        if regla == "FIFO":
            disponibles.sort(key=lambda x: (x['Llegada'], x['Orden_Original']))
        elif regla == "LIFO":
            disponibles.sort(key=lambda x: (x['Llegada'], -x['Orden_Original']), reverse=True)
        elif regla == "EDD":
            disponibles.sort(key=lambda x: (x['Entrega'], x['Proceso'], x['Orden_Original']))
        elif regla == "SPT":
            disponibles.sort(key=lambda x: (x['Proceso'], x['Entrega'], x['Orden_Original']))
        elif regla == "LPT":
            # Para LPT ordenamos de menor a mayor en desempate y luego de mayor a menor en proceso
            disponibles.sort(key=lambda x: (x['Entrega'], x['Orden_Original']))
            disponibles.sort(key=lambda x: x['Proceso'], reverse=True)
        elif regla == "MS":
            # Recálculo dinámico de Holgura Mínima: MS_i = d_i - t - p_i
            for t in disponibles:
                t['MS'] = t['Entrega'] - tiempo_actual - t['Proceso']
            disponibles.sort(key=lambda x: (x['MS'], x['Entrega'], x['Proceso'], x['Orden_Original']))
        elif regla == "CR":
            # Recálculo dinámico de Radio Crítico: CR_i = (d_i - t) / p_i
            for t in disponibles:
                t['CR'] = (t['Entrega'] - tiempo_actual) / t['Proceso']
                t['Holgura'] = t['Entrega'] - tiempo_actual - t['Proceso']
            disponibles.sort(key=lambda x: (x['CR'], x['Holgura'], x['Entrega'], x['Proceso'], x['Orden_Original']))
            
        seleccionado = disponibles[0]
        
        t_inicio = tiempo_actual
        t_proceso = seleccionado['Proceso']
        t_fin = tiempo_actual + t_proceso
        d_i = seleccionado['Entrega']
        
        secuencia.append({
            "Trabajo": seleccionado['Trabajo'],
            "Inicio": t_inicio,
            "Fin": t_fin,
            "Proceso": t_proceso,
            "Due Date": d_i,
            "Tardanza": max(0, t_fin - d_i),
            "Llegada": seleccionado['Llegada']
        })
        
        seleccionado['Estado'] = 'Completado'
        tiempo_actual = t_fin
        
    return pd.DataFrame(secuencia)

def calcular_kpis(df_seq):
    c_max = df_seq['Fin'].max()
    t_max = df_seq['Tardanza'].max()
    t_total = df_seq['Tardanza'].sum()
    u_total = (df_seq['Tardanza'] > 0).sum()
    sum_c = df_seq['Fin'].sum()
    c_prom = sum_c / len(df_seq)
    
    # Cálculo adaptativo de WIP según los tiempos de llegada
    min_r = df_seq['Llegada'].min()
    max_r = df_seq['Llegada'].max()
    
    if max_r == 0 and min_r == 0:
        wip = sum_c / c_max if c_max > 0 else 0
        formula_wip = "Fórmula usada: Σ Ci / Cmax (Todos r_i = 0)"
    else:
        denom = c_max - min_r
        wip = ((df_seq['Fin'] - df_seq['Llegada']).sum() / denom) if denom > 0 else 0
        formula_wip = "Fórmula usada: Σ(Ci - ri) / (Cmax - min(ri))"
        
    return [c_max, t_max, t_total, u_total, sum_c, c_prom, wip], formula_wip

# ==========================================
# 2. PANEL 1 — DATOS DE ENTRADA
# ==========================================
st.sidebar.header("PANEL 1 — Datos de Entrada")
uploaded_file = st.sidebar.file_uploader("Cargar desde Excel o CSV", type=['xlsx', 'csv'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            datos_ini = pd.read_csv(uploaded_file)
        else:
            datos_ini = pd.read_excel(uploaded_file)
    except Exception as e:
        st.sidebar.error(f"Error al cargar el archivo: {e}")
        datos_ini = pd.DataFrame({
            "Trabajo": ["A", "B", "C", "D", "E", "F"],
            "Llegada": [0, 0, 0, 0, 0, 0],
            "Proceso": [5, 7, 3, 12, 9, 11],
            "Entrega": [5, 9, 6, 15, 15, 14]
        })
else:
    # Datos de referencia del documento
    datos_ini = pd.DataFrame({
        "Trabajo": ["A", "B", "C", "D", "E", "F"],
        "Llegada": [0, 0, 0, 0, 0, 0],
        "Proceso": [5, 7, 3, 12, 9, 11],
        "Entrega": [5, 9, 6, 15, 15, 14]
    })

st.sidebar.write("Tabla editable de trabajos:")
df_trabajos = st.sidebar.data_editor(datos_ini, num_rows="dynamic")

# Validación simple de datos
if (df_trabajos['Proceso'] <= 0).any() or (df_trabajos['Llegada'] < 0).any():
    st.sidebar.warning("⚠️ Asegúrate de que los tiempos de proceso sean > 0 y los de llegada >= 0.")

# ==========================================
# 3. PROCESAMIENTO GENERAL DE TODAS LAS REGLAS
# ==========================================
reglas = ["FIFO", "EDD", "SPT", "LPT", "MS", "LIFO", "CR"]
indicadores = ["Makespan", "Tmax", "Tardanza Total", "Trabajos tardíos", "Σ Ci", "C promedio", "WIP promedio"]
resultados_todas = {}
metricas_todas = []
formula_wip_usada = ""

for r in reglas:
    df_res = calcular_secuencia(df_trabajos, r)
    resultados_todas[r] = df_res
    kpis, f_wip = calcular_kpis(df_res)
    metricas_todas.append(kpis)
    formula_wip_usada = f_wip

df_metricas = pd.DataFrame(metricas_todas, columns=indicadores, index=reglas).T

# Normalización para Gráfico Radial y Recomendación (0 a 100, 100 = Mejor)
df_norm = pd.DataFrame(index=reglas)
for col in indicadores:
    max_val = df_metricas.loc[col].max()
    min_val = df_metricas.loc[col].min()
    if max_val == min_val:
        df_norm[col] = 100
    else:
        # Todos los indicadores definidos son de minimización
        df_norm[col] = 100 * (max_val - df_metricas.loc[col]) / (max_val - min_val)

df_norm['Score_Total'] = df_norm.sum(axis=1)
mejor_regla = df_norm['Score_Total'].idxmax()

# ==========================================
# 4. INTERFAZ EN LA PÁGINA PRINCIPAL
# ==========================================
col1, col2 = st.columns([1, 1.1])

with col1:
    st.header("PANEL 2 — Resumen y Recomendación")
    regla_vista = st.selectbox("Seleccionar Regla para Inspeccionar:", reglas, index=reglas.index(mejor_regla))
    
    st.success(f"🏆 **Regla Recomendada Automáticamente:** **{mejor_regla}**")
    st.caption("*(Basado en la puntuación ponderada de indicadores normalizados)*")
    
    # Tarjetas KPI
    kpis_sel = df_metricas[regla_vista]
    k1, k2, k3 = st.columns(3)
    k1.metric("Makespan (Cmax)", f"{kpis_sel['Makespan']:.2f}")
    k2.metric("Tardanza Máx (Tmax)", f"{kpis_sel['Tmax']:.2f}")
    k3.metric("Tardanza Total", f"{kpis_sel['Tardanza Total']:.2f}")
    
    k4, k5, k6 = st.columns(3)
    k4.metric("Trabajos Tardíos", int(kpis_sel["Trabajos tardíos"]))
    k5.metric("C Promedio", f"{kpis_sel['C promedio']:.2f}")
    k6.metric("WIP Promedio", f"{kpis_sel['WIP promedio']:.2f}")
    st.info(f"ℹ️ {formula_wip_usada}")

with col2:
    st.header("PANEL 3 — Comparación Radial")
    # Gráfico Radial (Plotly)
    fig_radar = go.Figure()
    for r in reglas:
        valores_r = df_norm.loc[r, indicadores].tolist()
        fig_radar.add_trace(go.Scatterpolar(
            r=valores_r + [valores_r[0]],
            theta=indicadores + [indicadores[0]],
            fill='toself' if r == mejor_regla else 'none',
            name=r,
            visible=True if r in [mejor_regla, regla_vista] else 'legendonly'
        ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="Desempeño Normalizado (100 = Mejor Desempeño)",
        showlegend=True
    )
    st.plotly_chart(fig_radar, use_container_width=True)

st.divider()

# ==========================================
# 5. PANEL 4 — TABLA COMPARATIVA, SECUENCIA Y GANTT
# ==========================================
st.header("PANEL 4 — Comparación Global, Secuencia y Diagrama de Gantt")

tab1, tab2, tab3 = st.tabs(["📊 Tabla Comparativa de Indicadores", "📋 Vista de Secuencia", "⏱️ Diagrama de Gantt"])

with tab1:
    st.subheader("Tabla Comparativa (Verde = Mejor Desempeño)")
    # Se resaltan automáticamente los mejores valores (mínimos)
    st.dataframe(df_metricas.style.highlight_min(axis=1, color='lightgreen').format("{:.2f}"))

with tab2:
    df_sec_sel = resultados_todas[regla_vista]
    st.subheader(f"Secuencia Obtenida ({regla_vista}): {' → '.join(df_sec_sel['Trabajo'].tolist())}")
    st.dataframe(df_sec_sel)

with tab3:
    st.subheader(f"Diagrama de Gantt — {regla_vista}")
    
    opcion_gantt = st.radio("Modo de Visualización:", ["Regla Seleccionada", "Comparar Todas las Reglas"], horizontal=True)
    
    if opcion_gantt == "Regla Seleccionada":
        df_gantt_curr = resultados_todas[regla_vista].sort_values(by="Inicio", ascending=False)
        fig_gantt = go.Figure()
        
        for _, row in df_gantt_curr.iterrows():
            color = "#ef4444" if row["Tardanza"] > 0 else "#22c55e"
            estado = "Tardío" if row["Tardanza"] > 0 else "A tiempo"
            
            fig_gantt.add_trace(go.Bar(
                x=[row["Proceso"]],
                y=[row["Trabajo"]],
                base=[row["Inicio"]],
                orientation='h',
                marker_color=color,
                name=row["Trabajo"],
                hovertemplate=(f"<b>Trabajo {row['Trabajo']}</b><br>"
                               f"Regla: {regla_vista}<br>"
                               f"Inicio: {row['Inicio']}<br>"
                               f"Fin: {row['Fin']}<br>"
                               f"Proceso: {row['Proceso']}<br>"
                               f"Fecha Entrega: {row['Due Date']}<br>"
                               f"Tardanza: {row['Tardanza']}<br>"
                               f"Estado: {estado}<extra></extra>")
            ))
            # Marcador visual de Fecha de Entrega
            fig_gantt.add_trace(go.Scatter(
                x=[row["Due Date"]],
                y=[row["Trabajo"]],
                mode="markers",
                marker=dict(color="black", symbol="diamond", size=10),
                name="Fecha Entrega",
                showlegend=False,
                hoverinfo="skip"
            ))
            
        fig_gantt.update_layout(
            title=f"Gantt de {regla_vista} (Diamante Negro = Fecha de Entrega)",
            xaxis_title="Tiempo",
            yaxis_title="Trabajos",
            barmode='stack',
            showlegend=False
        )
        st.plotly_chart(fig_gantt, use_container_width=True)
        
    else:
        # Comparación general de Gantt para todas las reglas
        df_list = []
        for r_name, df_r in resultados_todas.items():
            df_temp = df_r.copy()
            df_temp['Regla'] = r_name
            df_list.append(df_temp)
        df_all_gantt = pd.concat(df_list)
        
        fig_all = px.timeline(
            df_all_gantt,
            x_start=pd.to_datetime(df_all_gantt['Inicio'], unit='D', origin='2026-01-01'),
            x_end=pd.to_datetime(df_all_gantt['Fin'], unit='D', origin='2026-01-01'),
            y="Regla",
            color="Trabajo",
            title="Comparación Multirregla de Secuencias"
        )
        fig_all.layout.xaxis.type = 'linear'
        for item in fig_all.data:
            item.x = df_all_gantt[df_all_gantt['Trabajo'] == item.name]['Proceso'].tolist()
            item.base = df_all_gantt[df_all_gantt['Trabajo'] == item.name]['Inicio'].tolist()
            
        st.plotly_chart(fig_all, use_container_width=True)

# ==========================================
# 6. SECCIÓN EDUCATIVA: ¿CÓMO FUNCIONA CADA REGLA?
# ==========================================
st.divider()
st.header("❓ ¿Cómo funciona cada regla?")
regla_info = st.selectbox("Selecciona una regla para ver su marco teórico:", reglas)

info_reglas = {
    "FIFO": {
        "Nombre": "First In First Out (Primero en llegar, primero en ser atendido)",
        "Formula": "Prioridad_i = r_i",
        "Criterio": "Ordena los trabajos en función de su tiempo de llegada en orden ascendente.",
        "Interpretacion": "Es el enfoque tradicional de colas de servicio. Garantiza equidad por orden de llegada pero ignora las fechas de entrega y los tiempos de procesamiento."
    },
    "LIFO": {
        "Nombre": "Last In First Out (Último en llegar, primero en ser atendido)",
        "Formula": "Prioridad_i = -r_i",
        "Criterio": "Ordena los trabajos inversamente a su tiempo de llegada.",
        "Interpretacion": "Prioriza los trabajos más recientes en ingresar al sistema."
    },
    "EDD": {
        "Nombre": "Earliest Due Date (Fecha de entrega más próxima)",
        "Formula": "Prioridad_i = d_i",
        "Criterio": "Prioriza el trabajo con la fecha de entrega más cercana.",
        "Interpretacion": "Excelente estrategia heurística para minimizar la tardanza máxima (Tmax)."
    },
    "SPT": {
        "Nombre": "Shortest Processing Time (Tiempo de procesamiento más corto)",
        "Formula": "Prioridad_i = p_i",
        "Criterio": "Prioriza los trabajos con menor tiempo de ejecución.",
        "Interpretacion": "Demostrado matemáticamente que minimiza el tiempo promedio de terminación (C promedio) y reduce el inventario en proceso (WIP)."
    },
    "LPT": {
        "Nombre": "Longest Processing Time (Tiempo de procesamiento más largo)",
        "Formula": "Prioridad_i = -p_i",
        "Criterio": "Prioriza los trabajos más largos primero.",
        "Interpretacion": "Útil para balancear cargas en entornos multimáquina, aunque suele penalizar los trabajos cortos en una sola máquina."
    },
    "MS": {
        "Nombre": "Minimum Slack (Holgura Mínima Dinámica)",
        "Formula": "MS_i = d_i - t - p_i",
        "Criterio": "Calcula en cada instante 't' el margen disponible antes del vencimiento. Selecciona min(MS_i).",
        "Interpretacion": "Si MS_i < 0, el trabajo ya está en riesgo de retraso. Se recalcula dinámicamente en cada despacho."
    },
    "CR": {
        "Nombre": "Critical Ratio (Radio Crítico Dinámico)",
        "Formula": "CR_i = (d_i - t) / p_i",
        "Criterio": "Calcula la razón entre el tiempo disponible y el tiempo necesario. Selecciona min(CR_i).",
        "Interpretacion": "CR < 1 indica que el trabajo se entregará tarde; CR = 1 está justo al límite; CR > 1 tiene margen de tiempo."
    }
}

i = info_reglas[regla_info]
st.subheader(i["Nombre"])
st.code(i["Formula"], language="latex")
st.write(f"**Criterio de Prioridad:** {i['Criterio']}")
st.write(f"**Interpretación Operacional:** {i['Interpretacion']}")
