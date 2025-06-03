import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import requests
from io import StringIO

st.set_page_config(layout="wide")

# -------------------------
# FUNCIONES AUXILIARES
# -------------------------

def cargar_datos_desde_sheets(sheet_url):
    response = requests.get(sheet_url, timeout=10)
    if response.status_code != 200:
        raise Exception("No se pudo acceder al archivo.")
    response.encoding = 'latin1'
    return pd.read_csv(StringIO(response.content.decode('utf-8')))

def color_semaforo(val):
    if val <= 12:
        color = '#C8E6C9'
    elif 13 <= val <= 20:
        color = '#FFF9C4'
    else:
        color = '#FFCDD2'
    return f'background-color: {color}; text-align: center;'

def color_por_carga(val):
    if val > 5:
        return "#EF5350"
    elif val >= 3:
        return "#FFEE58"
    else:
        return "#66BB6A"

# -------------------------
# CARGA DE DATOS
# -------------------------

default_sheet_url = "https://docs.google.com/spreadsheets/d/18uRbFCZ3btmnLxsfePyJ0_JURaxARa0hZl1ZbM9EQIY/export?format=csv&gid=1933021086"
sheet_url = default_sheet_url

try:
    df = cargar_datos_desde_sheets(sheet_url)
    df.columns = df.columns.str.strip()
    df.replace(["<5", "N/A", "—", "-", ""], np.nan, inplace=True)
    df = df.fillna(0)

    cols_to_numeric = [
        'Recruitment. Candidatos nuevos', 'Recruitment. Candidatos Indeed', 
        'Recruitment. Busqueda directa', 'Recruitment. Candidatos R.CRM', 
        'Recruitment. Assigned', 'Recruitment. Candidatos Viables',
        'Screening. CV. MUST', 'Screening. CV. H.Skills', 'Screening. CV. S.Skills',
        'Screening. CNV. Perfil no calificado (hard skills)', 'Screening. CNV. Soft Skills', 
        'Screening. CNV. Fuera de presupuesto', 'Screening. CNV. Nivel de ingles',
        'Screening. CNV. No se presento / Inpuntual', 'Screening. CNV. Localidad', 
        'S. Cliente. Quimica personal', 'S. Cliente. Inconsistencias en expertise',
        'S. Cliente. No cumple con el perfil', 'S. Cliente. Nivel de ingles',
        'S. Cliente. Sobrecalificado', 'Candidatos contratados'
    ]
    cols_to_numeric = [col for col in cols_to_numeric if col in df.columns]
    df[cols_to_numeric] = df[cols_to_numeric].apply(pd.to_numeric, errors='coerce').fillna(0)

    df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
    df = df[df["Fecha"].notna()]
    df["Posicion"] = df["Posicion"].astype(str)
    
except Exception as e:
    st.error(f"Error al cargar o procesar el archivo: {e}")

# -------------------------
# FILTROS GLOBALES
# -------------------------

st.title("Dashboard de Reclutamiento")

col_filtro_pos, col_filtro_periodo = st.columns([2, 1])
with col_filtro_pos:
    posicion_sel = st.selectbox("Filtrar por Posición", ["Todas"] + sorted(df["Posicion"].unique()))
with col_filtro_periodo:
    periodo = st.selectbox("Periodo", ["Diaria", "Semana", "Mes", "3 Meses", "Año"])

fecha_max = df["Fecha"].max()
if periodo == "Semana":
    fecha_inicio = fecha_max - pd.Timedelta(days=7)
elif periodo == "Mes":
    fecha_inicio = fecha_max - pd.DateOffset(months=1)
elif periodo == "3 Meses":
    fecha_inicio = fecha_max - pd.DateOffset(months=3)
elif periodo == "Año":
    fecha_inicio = fecha_max - pd.DateOffset(years=1)
else:
    fecha_inicio = fecha_max - pd.Timedelta(days=1)

df_filtrado = df[(df["Fecha"] >= fecha_inicio) & (df["Fecha"] <= fecha_max)]
if posicion_sel != "Todas":
    df_filtrado = df_filtrado[df_filtrado["Posicion"] == posicion_sel]

pagina = st.radio("Selecciona vista", ["Resumen General", "Evaluación y Conversión", "Posiciones cerradas"])

# -------------------------
# PÁGINA: RESUMEN GENERAL
# -------------------------

if pagina == "Resumen General":

    col1, col2 = st.columns([1, 2])

    with col1:
        fecha_apertura = df_filtrado["Fecha"].min()
        hoy = pd.Timestamp.today().normalize()
        dias = (hoy - fecha_apertura).days if pd.notna(fecha_apertura) else 0
        st.markdown("### 🚀 Velocidad de contratación")
        st.metric(label="Días desde apertura", value=f"{dias} días")

    with col2:
        st.markdown("### ⏱ Tiempo por posición")
        posiciones_con_datos = []
        for pos in df_filtrado["Posicion"].unique():
            fecha_pos = df_filtrado[df_filtrado["Posicion"] == pos]["Fecha"].min()
            dias_pos = (hoy - fecha_pos).days if pd.notna(fecha_pos) else 0
            posiciones_con_datos.append((pos, fecha_pos.date(), dias_pos))
        df_tiempos = pd.DataFrame(posiciones_con_datos, columns=["Posición", "Fecha apertura", "Días abiertos"])
        styled_df = df_tiempos.style.applymap(color_semaforo, subset=["Días abiertos"])
        st.dataframe(styled_df, use_container_width=True, height=220)

    col3, col4, col5 = st.columns([1.5, 1, 1])

    with col3:
        st.markdown("### 🎯 Embudo de reclutamiento")
        funnel_data = {
            "Indeed": df_filtrado["Recruitment. Candidatos Indeed"].sum(),
            "RCRM": df_filtrado["Recruitment. Candidatos R.CRM"].sum(),
            "Viables": df_filtrado["Recruitment. Candidatos Viables"].sum(),
            "Contratados": df_filtrado["Candidatos contratados"].sum()
        }
        fig, ax = plt.subplots(figsize=(5, 3))
        ax.barh(list(funnel_data.keys())[::-1], list(funnel_data.values())[::-1], color="#4C72B0")
        ax.set_xlabel("Candidatos")
        st.pyplot(fig)

    with col4:
        st.markdown("### 👥 Carga laboral")
        ultimos = df.loc[df.groupby("Posicion")["Fecha"].idxmax()]
        abiertas = ultimos[ultimos["¿Posicion abierta?"].astype(str).str.lower().str.strip() != "no"]
        resumen = abiertas.groupby("Nombre reclutador").size().reset_index(name="Posiciones abiertas")
        fig, ax = plt.subplots(figsize=(4, 3))
        colores = [color_por_carga(x) for x in resumen["Posiciones abiertas"]]
        ax.bar(resumen["Nombre reclutador"], resumen["Posiciones abiertas"], color=colores)
        plt.xticks(rotation=45)
        st.pyplot(fig)

    with col5:
        st.markdown("### 🔎 Abiertas >30 días")
        abiertas["Días_abierta"] = (hoy - abiertas["Fecha"]).dt.days
        alerta = abiertas[abiertas["Días_abierta"] > 30]
        st.dataframe(alerta[["Posicion", "Nombre reclutador", "Días_abierta"]], height=200, use_container_width=True)

# -------------------------
# PÁGINA: EVALUACIÓN Y CONVERSIÓN
# -------------------------

elif pagina == "Evaluación y Conversión":

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 📊 Tendencia diaria")
        daily = df_filtrado.groupby("Fecha")[["Recruitment. Candidatos Indeed", "Recruitment. Busqueda directa"]].sum()
        fechas = daily.index
        x = np.arange(len(fechas))
        fig, ax = plt.subplots(figsize=(7, 3))
        ax.bar(x, daily["Recruitment. Candidatos Indeed"], label="Indeed", color="#42A5F5")
        ax.bar(x, daily["Recruitment. Busqueda directa"], bottom=daily["Recruitment. Candidatos Indeed"], color="#66BB6A", label="Directa")
        ax.set_xticks(x)
        ax.set_xticklabels([f.strftime("%Y-%m-%d") for f in fechas], rotation=45)
        ax.legend()
        st.pyplot(fig)

    with col2:
        st.markdown("### 🔍 Descartes")
        etapa2 = {
            "Hard Skills": df_filtrado["Screening. CNV. Perfil no calificado (hard skills)"].sum(),
            "Fuera presupuesto": df_filtrado["Screening. CNV. Fuera de presupuesto"].sum(),
            "Soft Skills": df_filtrado["Screening. CNV. Soft Skills"].sum(),
            "Inglés": df_filtrado["Screening. CNV. Nivel de ingles"].sum(),
            "No show": df_filtrado["Screening. CNV. No se presento / Inpuntual"].sum(),
            "Localidad": df_filtrado["Screening. CNV. Localidad"].sum()
        }
        etapa2 = {k: v for k, v in etapa2.items() if v > 0}
        fig2, ax2 = plt.subplots(figsize=(3,3))
        ax2.pie(etapa2.values(), labels=etapa2.keys(), autopct='%1.1f%%')
        ax2.axis('equal')
        st.pyplot(fig2)

# -------------------------
# PÁGINA: POSICIONES CERRADAS
# -------------------------

elif pagina == "Posiciones cerradas":

    ultimos = df.loc[df.groupby("Posicion")["Fecha"].idxmax()]
    cerradas = ultimos[ultimos["¿Posicion abierta?"].astype(str).str.lower().str.strip() == "no"]

    fechas_apertura = df.groupby("Posicion")["Fecha"].min().reset_index().rename(columns={"Fecha": "Fecha_apertura"})
    cerradas = cerradas.merge(fechas_apertura, on="Posicion")
    cerradas["Dias_para_cerrar"] = (cerradas["Fecha"] - cerradas["Fecha_apertura"]).dt.days

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("### ⏱ Tiempo de cierre")
        st.dataframe(cerradas[["Posicion", "Nombre reclutador", "Dias_para_cerrar"]], height=250)

    with col2:
        st.markdown("### ✅ Conversión cerradas")
        posiciones_cerradas = cerradas["Posicion"].tolist()
        df_cerradas = df[df["Posicion"].isin(posiciones_cerradas)]
        conversion_data = df_cerradas.groupby("Posicion")[["Recruitment. Candidatos Viables", "Candidatos contratados"]].sum()
        conversion_data["Conversion"] = (conversion_data["Candidatos contratados"] / conversion_data["Recruitment. Candidatos Viables"]).fillna(0) * 100
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.barh(conversion_data.index, conversion_data["Conversion"], color="#4CAF50")
        st.pyplot(fig)

    st.markdown("### 🔬 Descarte por reclutador (cerradas)")
    descarte_por_reclutador = df_cerradas.groupby("Nombre reclutador")[[
        "Screening. CNV. Perfil no calificado (hard skills)",
        "Screening. CNV. Soft Skills",
        "Screening. CNV. Fuera de presupuesto",
        "Screening. CNV. Nivel de ingles",
        "Screening. CNV. No se presento / Inpuntual",
        "Screening. CNV. Localidad"
    ]].sum()
    fig, ax = plt.subplots(figsize=(8, 3))
    descarte_por_reclutador.plot(kind='bar', stacked=True, ax=ax)
    plt.xticks(rotation=45)
    st.pyplot(fig)
