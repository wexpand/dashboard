import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import requests
from io import StringIO
from pandas.tseries.offsets import BDay
import matplotlib.dates as mdates

st.set_page_config(layout="wide")

# INYECCIÓN GLOBAL DE ESTILO DEL DASHBOARD DE RECLUTAMIENTO

st.markdown("""
<style>

    /* ----- BACKGROUND GENERAL ----- */
    .stApp {
        background-color: #F9F9F9;
    }

    /* ----- COLOR GENERAL DE TEXTOS ----- */
    html, body, div, p, label {
        color: #2C3E50;
        font-family: 'Segoe UI', 'Roboto', sans-serif;
        font-weight: 400;
    }

    /* ----- TITULOS Y HEADERS ----- */
    h1, h2, h3, h4 {
        color: #2C3E50 !important;
        font-weight: 700 !important;
    }

    /* ----- SIDEBAR ----- */
    section[data-testid="stSidebar"] {
        background-color: #ECEFF4;
        border-right: 1px solid #D0D7DE;
    }

    /* ----- SELECTBOX ----- */
    div[data-baseweb="select"] > div {
        background-color: #F5F9FF !important;
        border-radius: 8px !important;
        border: 1px solid #2980B9 !important;
    }
    
    div[data-baseweb="select"] div[class*="Text"] {
        color: #2C3E50 !important;
        font-weight: 600 !important;
    }

    label {
        color: #2C3E50 !important;
        font-weight: 700 !important;
        font-size: 16px !important;
    }

    /* ----- METRICS (los KPIs) ----- */
    div[data-testid="metric-container"] {
        background-color: #E3F2FD;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #BBDEFB;
        color: #2C3E50;
    }

    /* ----- TABLAS ----- */
    .stDataFrame {
        background-color: #FFFFFF !important;
        border-radius: 10px;
        border: 1px solid #E0E0E0;
    }

    /* ----- BOTONES ----- */
    div.stButton > button {
        background-color: #2980B9;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 10px 20px;
        border: none;
    }

    div.stButton > button:hover {
        background-color: #21618C;
        color: white;
    }

</style>
""", unsafe_allow_html=True)


# --- FUNCIONES AUXILIARES ---
def cargar_datos_desde_sheets(sheet_url):
    response = requests.get(sheet_url, timeout=10)
    if response.status_code != 200:
        raise Exception("No se pudo acceder al archivo.")
    response.encoding = 'latin1'
    return pd.read_csv(StringIO(response.content.decode('utf-8')))

def filtrar_datos(df, fecha_inicio, fecha_fin, posicion):
    df = df.dropna(subset=["Fecha"])
    df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
    fecha_inicio = pd.to_datetime(fecha_inicio, dayfirst=True, errors="coerce")
    fecha_fin = pd.to_datetime(fecha_fin, dayfirst=True, errors="coerce")

    if pd.isna(fecha_inicio) or pd.isna(fecha_fin):
        st.error("Las fechas seleccionadas no son válidas.")
        st.stop()

    df = df[df["Fecha"].notna()]
    df = df[(df["Fecha"] >= fecha_inicio) & (df["Fecha"] <= fecha_fin)]

    if posicion != "Todas":
        df = df[df["Posicion"] == posicion]

    return df

def color_semaforo(val):
    if val <= 8:
        color = '#9eeb50'
    elif 8 <= val <= 12:
        color = '#ebde50'
    elif 12 <= val <= 20:
        color = '#eba050'
    else:
        color = '#eb5050'
    return f'background-color: {color}; text-align: center;'

def color_por_carga(val):
    if val > 5:
        return "#EF5350"
    elif val >= 3:
        return "#FFEE58"
    else:
        return "#66BB6A"

# Función de color por tipo de alerta
def color_alerta(val):
    val = str(val)
    if "Estado crítico" in val:
        color = '#e84646'  # Rojo
    elif "LinkedIn" in val:
        color = '#ed80cc'  # Rosa
    elif "WhatsApp" in val:
        color = '#ed8f80'  # Naranja
    elif "Instantly" in val:
        color = '#ede880'  # Amarillo
    elif "OK" in val:
        color = '#d7ed80'  # Verde
    else:
        color = '#FFFFFF'  # Blanco por default (si algo falla)
    return f'background-color: {color}; font-weight: bold;'

# Creamos la función para evaluar las alertas de sourcing
def evaluar_alertas_sourcing(df):
    
    # Primero calculamos fecha de apertura por posición
    fechas_apertura = df.groupby("Posicion")["Fecha"].min().reset_index().rename(columns={"Fecha": "Fecha_apertura"})
    # Calculamos días hábiles desde apertura para TODAS LAS POSICIONES
    hoy = pd.Timestamp.today().normalize()
    fechas_apertura["Dias_habiles_abierta"] = fechas_apertura["Fecha_apertura"].apply(
        lambda apertura: np.busday_count(apertura.date(), hoy.date())
    )
    
    # Unimos la fecha de apertura al dataframe principal
    df = df.merge(fechas_apertura, on="Posicion", how="left")
    
    # Calculamos días hábiles desde la apertura hasta la fecha actual
    hoy = pd.Timestamp.today().normalize()
    df["Dias_habiles"] = df.apply(lambda row: np.busday_count(row["Fecha_apertura"].date(), hoy.date()), axis=1)
    
    # Agrupamos por posición para calcular acumulados
    acumulados = df.groupby("Posicion").agg({
        "Fecha_apertura": "first",
        "Nombre reclutador": "first",
        "Dias_habiles": "first",
        "Recruitment. Candidatos Indeed": "first",  # sólo usamos el valor inicial
        "Recruitment. Candidatos nuevos": "sum"     # acumulamos los nuevos
    }).reset_index()

    # Ahora aplicamos las reglas de negocio
    def determinar_alerta(row):
        dias = row["Dias_habiles"]
        candidatos_indeed = row["Recruitment. Candidatos Indeed"]
        nuevos = row["Recruitment. Candidatos nuevos"]
        acumulado_total = candidatos_indeed + nuevos
        
        if dias >= 1 and candidatos_indeed < 30:
            return "Es necesario lanzar una campaña en Instantly"
        elif dias >= 3 and acumulado_total < 50:
            return "Te recomiendo una campaña por WhatsApp"
        elif dias >= 4 and acumulado_total < 60:
            return "Necesitas una campaña de LinkedIn"
        elif dias >= 5 and acumulado_total < 80:
            faltan = 80 - acumulado_total
            return f"Estado crítico: hay actualmente {acumulado_total} candidatos, faltan {faltan}. Iniciar búsqueda directa"
        else:
            return "Sin alertas - sourcing OK"
    
    acumulados["Alerta sourcing"] = acumulados.apply(determinar_alerta, axis=1)

    return acumulados[[
        "Posicion", "Alerta sourcing"
    ]]


# --- INTERFAZ DE USUARIO ---
st.title("Dashboard de Reclutamiento")

# URL por defecto
default_sheet_url = "https://docs.google.com/spreadsheets/d/18uRbFCZ3btmnLxsfePyJ0_JURaxARa0hZl1ZbM9EQIY/export?format=csv&gid=1933021086"

# Mostrar opción para personalizar el link
#st.sidebar.markdown("### Configuración")
#usar_url_personalizada = st.sidebar.checkbox("Usar Google Sheet personalizado")

#if usar_url_personalizada:
#    sheet_url = st.sidebar.text_input("Pega aquí el link CSV de Google Sheets:")
#else:

sheet_url = default_sheet_url

if sheet_url:
    try:
        #Primera limpieza general y filtrado de datos
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
        fecha_min = df["Fecha"].min()
        fecha_max = df["Fecha"].max()
        df["Posicion"] = df["Posicion"].astype(str)

        #Filtros para seleccionar páginas y más cosas
        #pagina = st.radio("Selecciona vista", ["Resumen General", "Evaluación y Conversión", "Posiciones cerradas"])

        #Primera parte del dashboard
        f_posicion, f_periodo, f_vista = st.columns(3)
        with f_posicion:
            posicion_sel = st.selectbox("Filtrar por Posición", ["Todas"] + sorted(df["Posicion"].unique()))
        with f_periodo:
            periodo = st.selectbox("Periodo", ["Semana", "Mes", "3 Meses", "Año"])
        with f_vista:
            pagina = st.selectbox("Selecciona vista", ["Resumen General", "Evaluación y Conversión", "Posiciones cerradas"])

        if periodo == "Semana":
            fecha_inicio = fecha_max - pd.Timedelta(days=7)
        elif periodo == "Mes":
            fecha_inicio = fecha_max - pd.DateOffset(months=1)
        elif periodo == "3 Meses":
            fecha_inicio = fecha_max - pd.DateOffset(months=3)
        else:
            fecha_inicio = fecha_max - pd.DateOffset(years=1)

        #Este df filtrado solo se tiene que usar para los KPIs no para las alertas
        df_filtrado = filtrar_datos(df, fecha_inicio, fecha_max, posicion_sel)

        #Procesos anteriores para agrupar por ternas
        # Calculamos apertura de cada posición
        fechas_apertura = df.groupby("Posicion")["Fecha"].min().reset_index().rename(columns={"Fecha": "Fecha_apertura"})

        # Aquí agregamos los días hábiles para TODAS las posiciones
        hoy = pd.Timestamp.today().normalize()
        fechas_apertura["Dias_habiles_abierta"] = fechas_apertura["Fecha_apertura"].apply(
            lambda apertura: np.busday_count(apertura.date(), hoy.date())
        )


        # Filtramos los registros donde efectivamente hubo envío de terna
        df_ternas = df[df["Terna"] > 0].copy()

        # Mergeamos para agregar la fecha de apertura a cada envío de terna
        df_ternas = df_ternas.merge(fechas_apertura, on="Posicion", how="left")

        # Calculamos días hábiles desde apertura a cada envío de terna
        df_ternas["Dias_habiles_a_terna"] = df_ternas.apply(
            lambda row: np.busday_count(row["Fecha_apertura"].date(), row["Fecha"].date()), axis=1
        )

        # Resumimos por posición:
        resumen_ternas = df_ternas.groupby("Posicion").agg({
            "Nombre reclutador": "first",
            "Fecha_apertura": "first",
            "Fecha": list,
            "Dias_habiles_a_terna": list,
            "Terna": list
        }).reset_index()

        # Agregamos total de ternas enviadas y total de candidatos enviados
        resumen_ternas["Total ternas enviadas"] = resumen_ternas["Fecha"].apply(len)
        resumen_ternas["Total candidatos enviados"] = resumen_ternas["Terna"].apply(sum)

        # Reordenamos columnas para visualización
        resumen_final = resumen_ternas[[
            "Posicion", "Nombre reclutador", "Fecha_apertura", 
            "Total ternas enviadas", "Total candidatos enviados", 
            "Fecha", "Dias_habiles_a_terna", "Terna"
        ]]

        resumen_tabla = resumen_ternas[[
            "Posicion", "Nombre reclutador", "Fecha_apertura",
            "Total ternas enviadas", "Total candidatos enviados"
        ]]
        # Merge para incluir días hábiles a la tabla de detalle
        resumen_tabla = resumen_tabla.merge(
            fechas_apertura[["Posicion", "Dias_habiles_abierta"]],
            on="Posicion",
            how="left"
        )


        #Organizacipon visual de la primera página 
        if pagina == "Resumen General":
            
            # Normalizamos los campos antes de procesar
            df["¿Posicion abierta?"] = df["¿Posicion abierta?"].astype(str).str.lower().str.strip()
            df["Nombre reclutador"] = df["Nombre reclutador"].astype(str).str.strip()
            df["Posicion"] = df["Posicion"].astype(str).str.strip()
            
            # Eliminar registros sin fecha válida
            df = df.dropna(subset=["Fecha"])
            
            # Agrupamos por posición y tomamos el registro más reciente
            ultimos = df.loc[df.groupby("Posicion")["Fecha"].idxmax()]
            
            # Filtrar posiciones abiertas
            abiertas = ultimos[ultimos["¿Posicion abierta?"] != "no"]
            
            # Agrupamos correctamente por reclutador
            resumen = abiertas.groupby("Nombre reclutador").size().reset_index(name="Posiciones abiertas")
            posiciones_por_reclutador = abiertas.groupby("Nombre reclutador")["Posicion"].apply(list).reset_index(name="Lista de posiciones")
            resumen_completo = pd.merge(resumen, posiciones_por_reclutador, on="Nombre reclutador")

            carga_trabajo, pos_reclutador = st.columns([1,2])

            # Primero preparamos los datos planos para graficar
            ternas_explotadas = []

            for idx, row in resumen_final.iterrows():
                for fecha_ts, dias_habiles, terna in zip(row["Fecha"], row["Dias_habiles_a_terna"], row["Terna"]):
                    fecha_real = pd.to_datetime(fecha_ts, unit='ms')  # Convertimos timestamp a fecha legible
                    ternas_explotadas.append({
                        "Posicion": row["Posicion"],
                        "Reclutador": row["Nombre reclutador"],
                        "Fecha": fecha_real,
                        "Dias_habiles": dias_habiles,
                        "Terna": terna
                })

            ternas_df = pd.DataFrame(ternas_explotadas)

            with carga_trabajo:
                st.markdown("### Carga laboral por reclutador")
                fig, ax = plt.subplots(figsize=(5, 3))
                colores = [color_por_carga(x) for x in resumen_completo["Posiciones abiertas"]]
                ax.bar(resumen_completo["Nombre reclutador"], resumen_completo["Posiciones abiertas"], color=colores)
                ax.set_ylabel("Posiciones abiertas")
                ax.set_xlabel("Reclutador")
                ax.grid(True)
                plt.xticks(rotation=45)
                st.pyplot(fig)
            
            with pos_reclutador:
                st.markdown("### Detalle de posiciones abiertas")
                st.dataframe(resumen_tabla, use_container_width=True, height=500)

            # Evaluamos sourcing health
            alertas_sourcing = evaluar_alertas_sourcing(df)
            
            ternas, alertas = st.columns([2,1])
            with ternas:
                st.markdown("### Envío de ternas por posición")

                # Creamos el gráfico
                plt.figure(figsize=(12, 6))
                for posicion in ternas_df["Posicion"].unique():
                    subset = ternas_df[ternas_df["Posicion"] == posicion]
                    plt.scatter(
                        subset["Dias_habiles"],
                        [posicion] * len(subset),
                        s=subset["Terna"] * 50,  # Tamaño proporcional al número de candidatos
                        label=posicion,
                        alpha=0.7
                    )

                plt.xlabel("Días hábiles desde apertura")
                plt.ylabel("Posición")
                #plt.title("Envío de ternas por posición")
                plt.grid(True)
                #plt.legend(title="Posiciones", bbox_to_anchor=(1.05, 1), loc='upper left')
                st.pyplot(plt)
            with alertas:
                # Mostramos en el dashboard
                st.markdown("### Alertas del día")
                styled_alertas = alertas_sourcing.style.applymap(color_alerta, subset=["Alerta sourcing"])
                st.dataframe(styled_alertas, use_container_width=True, height=500)

                
        #Segunda página
        elif pagina == "Evaluación y Conversión":
            
            d_reclutador, d_cliente, flujo_diario = st.columns([1,1,2])
            with d_reclutador:
                st.markdown("### Descarte por reclutadores")
                etapa2 = {
                    "Hard Skills": df.get("Screening. CNV. Perfil no calificado (hard skills)", pd.Series([0])).sum(),
                    "Fuera de presupuesto": df.get("Screening. CNV. Fuera de presupuesto", pd.Series([0])).sum(),
                    "Soft Skills": df.get("Screening. CNV. Soft Skills", pd.Series([0])).sum(),
                    "Inglés": df.get("Screening. CNV. Nivel de ingles", pd.Series([0])).sum(),
                    "No se presentó": df.get("Screening. CNV. No se presento / Inpuntual", pd.Series([0])).sum(),
                    "Localidad": df.get("Screening. CNV. Localidad", pd.Series([0])).sum()
                }
                etapa2 = {k: v for k, v in etapa2.items() if v > 0}
                if etapa2:
                    fig3, ax3 = plt.subplots(figsize=(8, 4.5))
                    ax3.pie(etapa2.values(), labels=etapa2.keys(), autopct='%1.1f%%', startangle=140, colors=plt.get_cmap('Pastel1').colors)
                    ax3.axis('equal')
                    st.pyplot(fig3)
                    plt.tight_layout(pad=2.0)


            with d_cliente:
                st.markdown("### Descartes por cliente")
                etapa3 = {
                    "Química": df.get("S. Cliente. Quimica personal", pd.Series([0])).sum(),
                    "Inconsistencias": df.get("S. Cliente. Inconsistencias en expertise", pd.Series([0])).sum(),
                    "Perfil": df.get("S. Cliente. No cumple con el perfil", pd.Series([0])).sum(),
                    "Inglés": df.get("S. Cliente. Nivel de ingles", pd.Series([0])).sum(),
                    "Sobrecalificado": df.get("S. Cliente. Sobrecalificado", pd.Series([0])).sum()
                }
                etapa3 = {k: v for k, v in etapa3.items() if v > 0}
                if etapa3:
                    fig4, ax4 = plt.subplots(figsize=(8, 4.5))
                    ax4.pie(etapa3.values(), labels=etapa3.keys(), autopct='%1.1f%%', startangle=140, colors=plt.get_cmap('Pastel2').colors)
                    ax4.axis('equal')
                    st.pyplot(fig4) 
                    plt.tight_layout(pad=2.0)

            with flujo_diario:
                st.markdown("### Flujo diario de candidatos")
                by_date = df_filtrado.groupby("Fecha")[["Recruitment. Candidatos nuevos", "Recruitment. Candidatos Viables", "Candidatos contratados"]].sum()
                if not by_date.empty:
                    fig6, ax6 = plt.subplots(figsize=(12, 4.5))
                    by_date.plot(ax=ax6)
                    ax6.set_title("Flujo diario de candidatos")
                    ax6.set_xlabel("Fecha")
                    ax6.set_ylabel("Cantidad")
                    ax6.grid(True)
                    st.pyplot(fig6)
                    plt.tight_layout(pad=2.0)

            tendencias, embudo, conversion = st.columns(3)
            with tendencias:
                st.markdown("### Tendencia diaria por fuente vs. metas")

                daily = df_filtrado.groupby("Fecha")[["Recruitment. Candidatos Indeed", "Recruitment. Busqueda directa"]].sum()
                daily = daily.sort_index()
                fechas = daily.index
                num_dias = len(fechas)

                # Metas por día (ajustadas por acumulación)
                meta_diaria = {
                    "Recruitment. Candidatos Indeed": 10,
                    "Recruitment. Busqueda directa": 2
                }

                metas_acumuladas = {
                    "Recruitment. Candidatos Indeed": [meta_diaria["Recruitment. Candidatos Indeed"] * (i+1) for i in range(num_dias)],
                    "Recruitment. Busqueda directa": [meta_diaria["Recruitment. Busqueda directa"] * (i+1) for i in range(num_dias)]
                }

                fig, ax = plt.subplots(figsize=(8, 4.5))

                x = np.arange(num_dias)

                # Barras apiladas
                bar1 = ax.bar(x, daily["Recruitment. Candidatos Indeed"], label="Recruitment. Candidatos Indeed", color="#42A5F5")
                bar2 = ax.bar(x, daily["Recruitment. Busqueda directa"], bottom=daily["Recruitment. Candidatos Indeed"], label="Recruitment. Busqueda directa", color="#66BB6A")

                # Líneas de metas
                ax.plot(x, metas_acumuladas["Recruitment. Candidatos Indeed"], color="#FF7043", linestyle="--", linewidth=2.5, marker='o', markersize=4, label="Meta Indeed")
                ax.plot(x, metas_acumuladas["Recruitment. Busqueda directa"], color="#AB47BC", linestyle="--", linewidth=2.5, marker='o', markersize=4, label="Meta Búsqueda directa")

                # Etiquetas
                for i, total in enumerate(daily.sum(axis=1)):
                    ax.text(i, total + 2, str(int(total)), ha='center', fontsize=9, weight='bold')

                ax.set_xticks(x)
                ax.set_xticklabels([fecha.strftime("%Y-%m-%d") for fecha in fechas], rotation=45)
                ax.set_ylabel("Candidatos")
                ax.set_xlabel("Fecha")
                ax.set_title("Tendencia diaria por fuente vs. metas", fontsize=14, weight="bold")
                ax.legend()
                ax.grid(axis='y', linestyle=':', alpha=0.6)
                plt.tight_layout(pad=2.0)

                st.pyplot(fig)

            with embudo:
                st.markdown("### Embudo de Reclutamiento")
                # Primero tomamos el último registro de cada posición
                ultimos_por_posicion = df_filtrado.loc[df_filtrado.groupby("Posicion")["Fecha"].idxmax()]

                # Luego sumamos los valores globales de esos últimos registros
                funnel_data = {
                    "Indeed": ultimos_por_posicion.get("Recruitment. Candidatos Indeed", pd.Series([0])).sum(),
                    "RCRM": ultimos_por_posicion.get("Recruitment. Candidatos R.CRM", pd.Series([0])).sum(),
                    "Viables": ultimos_por_posicion.get("Recruitment. Candidatos Viables", pd.Series([0])).sum(),
                    "Contratados": ultimos_por_posicion.get("Candidatos contratados", pd.Series([0])).sum()
                }

                # Graficamos como antes
                fig2, ax2 = plt.subplots(figsize=(12, 10))
                ax2.barh(list(funnel_data.keys())[::-1], list(funnel_data.values())[::-1], color="#4C72B0")
                ax2.set_title("Embudo de Reclutamiento (última actualización por posición)")
                ax2.set_xlabel("Cantidad de Candidatos")
                plt.tight_layout(pad=2.0)
                st.pyplot(fig2)
         

            with conversion:
                st.markdown("### Conversión de Viables a Contratados")
                by_vacancy = df.groupby("Posicion")[["Recruitment. Candidatos nuevos", "Recruitment. Candidatos Viables", "Candidatos contratados"]].sum()
                if not by_vacancy.empty:
                    conversion = (by_vacancy["Candidatos contratados"] / by_vacancy["Recruitment. Candidatos Viables"]).fillna(0) * 100
                    conversion = conversion[conversion > 0]
                    if not conversion.empty:
                        fig5, ax5 = plt.subplots(figsize=(8,4.5))
                        ax5.barh(conversion.index, conversion.values, color="#C44E52")
                        ax5.set_title("Tasa de Conversión de Viables a Contratados")
                        ax5.set_xlabel("% Conversión")
                        plt.tight_layout(pad=2.0)
                        st.pyplot(fig5)       

        elif pagina == "Posiciones cerradas":
            st.markdown("## Posiciones cerradas")
        
            # Normalizamos y preparamos datos
            df["¿Posicion abierta?"] = df["¿Posicion abierta?"].astype(str).str.lower().str.strip()
            df["Nombre reclutador"] = df["Nombre reclutador"].astype(str).str.strip()
            df["Posicion"] = df["Posicion"].astype(str).str.strip()
            df = df.dropna(subset=["Fecha"])
            df["Fecha"] = pd.to_datetime(df["Fecha"], dayfirst=True, errors="coerce")
        
            # Tomamos el último registro por posición
            ultimos = df.loc[df.groupby("Posicion")["Fecha"].idxmax()]
        
            # Solo posiciones cerradas
            cerradas = ultimos[ultimos["¿Posicion abierta?"] == "no"]
        
            # Obtenemos fecha de apertura para cada posición
            fechas_apertura = df.groupby("Posicion")["Fecha"].min().reset_index().rename(columns={"Fecha": "Fecha_apertura"})
            hoy = pd.Timestamp.today().normalize()
            fechas_apertura["Dias_habiles_abierta"] = fechas_apertura["Fecha_apertura"].apply(
                lambda apertura: np.busday_count(apertura.date(), hoy.date())
            )
        
            # Mergeamos para tener apertura y cierre
            cerradas = cerradas.merge(fechas_apertura, on="Posicion")
            cerradas["Dias_para_cerrar"] = (cerradas["Fecha"] - cerradas["Fecha_apertura"]).dt.days
        
            # Mostramos tabla de tiempos de cierre
            st.markdown("### Tiempo de cierre por posición")
            st.dataframe(cerradas[["Posicion", "Nombre reclutador", "Fecha_apertura", "Fecha", "Dias_para_cerrar"]], use_container_width=True)
        
            # Conversiones sobre las posiciones cerradas
            posiciones_cerradas = cerradas["Posicion"].tolist()
            df_cerradas = df[df["Posicion"].isin(posiciones_cerradas)]
        
            st.markdown("### Conversión en posiciones cerradas")
            conversion_data = df_cerradas.groupby("Posicion")[["Recruitment. Candidatos Viables", "Candidatos contratados"]].sum()
        
            if not conversion_data.empty:
                conversion_data["Conversion"] = (conversion_data["Candidatos contratados"] / conversion_data["Recruitment. Candidatos Viables"]).fillna(0) * 100
                conversion_data = conversion_data.sort_values("Conversion", ascending=False)
        
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.barh(conversion_data.index, conversion_data["Conversion"], color="#4CAF50")
                ax.set_xlabel("% de Conversión")
                ax.set_title("Conversión por posición cerrada")
                st.pyplot(fig)
            else:
                st.info("No hay datos suficientes para calcular la conversión.")
        
            # Descarte por reclutador (solo cerradas)
            st.markdown("### Descarte por reclutador (solo posiciones cerradas)")
            descarte_por_reclutador = df_cerradas.groupby("Nombre reclutador")[[
                "Screening. CNV. Perfil no calificado (hard skills)",
                "Screening. CNV. Soft Skills",
                "Screening. CNV. Fuera de presupuesto",
                "Screening. CNV. Nivel de ingles",
                "Screening. CNV. No se presento / Inpuntual",
                "Screening. CNV. Localidad"
            ]].sum()
        
            if not descarte_por_reclutador.empty:
                fig, ax = plt.subplots(figsize=(12, 6))
                descarte_por_reclutador.plot(kind='bar', stacked=True, ax=ax)
                ax.set_ylabel("Cantidad de descartes")
                ax.set_title("Razones de descarte por reclutador")
                plt.xticks(rotation=45)
                st.pyplot(fig)
            else:
                st.info("No hay datos de descartes en posiciones cerradas.")

    
    except Exception as e:
        st.error(f"Error al cargar o procesar el archivo: {e}")
