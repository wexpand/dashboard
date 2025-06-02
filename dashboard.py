import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import requests
from io import StringIO

st.set_page_config(layout="wide")

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

# --- INTERFAZ DE USUARIO ---
st.title("Dashboard de Reclutamiento")

# URL por defecto
default_sheet_url = "https://docs.google.com/spreadsheets/d/18uRbFCZ3btmnLxsfePyJ0_JURaxARa0hZl1ZbM9EQIY/export?format=csv&gid=1933021086"

# Mostrar opción para personalizar el link
st.sidebar.markdown("### Configuración")
usar_url_personalizada = st.sidebar.checkbox("Usar Google Sheet personalizado")

if usar_url_personalizada:
    sheet_url = st.sidebar.text_input("Pega aquí el link CSV de Google Sheets:")
else:
    sheet_url = default_sheet_url


pagina = st.radio("Selecciona vista", ["Resumen General", "Evaluación y Conversión"])

if sheet_url:
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
        fecha_min = df["Fecha"].min()
        fecha_max = df["Fecha"].max()

        df["Posicion"] = df["Posicion"].astype(str)
        posicion_sel = st.selectbox("Filtrar por Posición", ["Todas"] + sorted(df["Posicion"].unique()))
        periodo = st.selectbox("Periodo", ["Semana", "Mes", "3 Meses", "Año"])

        if periodo == "Semana":
            fecha_inicio = fecha_max - pd.Timedelta(days=7)
        elif periodo == "Mes":
            fecha_inicio = fecha_max - pd.DateOffset(months=1)
        elif periodo == "3 Meses":
            fecha_inicio = fecha_max - pd.DateOffset(months=3)
        else:
            fecha_inicio = fecha_max - pd.DateOffset(years=1)


        df_filtrado = filtrar_datos(df, fecha_inicio, fecha_max, posicion_sel)

        if pagina == "Resumen General":
            
            st.markdown("### Flujo diario de candidatos")
            by_date = df_filtrado.groupby("Fecha")[["Recruitment. Candidatos nuevos", "Recruitment. Candidatos Viables", "Candidatos contratados"]].sum()
            if not by_date.empty:
                fig6, ax6 = plt.subplots(figsize=(12, 3))
                by_date.plot(ax=ax6)
                ax6.set_title("Flujo diario de candidatos")
                ax6.set_xlabel("Fecha")
                ax6.set_ylabel("Cantidad")
                st.pyplot(fig6)

            col1, col2 = st.columns([1, 2])
            with col1:
                # Fecha de apertura: primer registro en el dataset filtrado
                fecha_apertura = df_filtrado["Fecha"].min()
                
                # Fecha de contratación: última contratación registrada
                ultima_contrata = df_filtrado[df_filtrado["Candidatos contratados"] > 0]["Fecha"].max()
                
                st.markdown("### Velocidad de contratación")

                if pd.isna(fecha_apertura) and pd.isna(ultima_contrata):
                    st.info("No hay datos de posiciones abiertas ni contrataciones en el período seleccionado.")
                elif pd.isna(fecha_apertura):
                    st.info("No hay datos de posiciones abiertas en el período seleccionado.")
                elif pd.isna(ultima_contrata):
                    st.info("No hay contrataciones registradas en el período seleccionado.")
                else:
                    dias = (ultima_contrata - fecha_apertura).days
                    
                    if dias > 12:
                        st.markdown(f"""
                        <div style='padding:1em; background-color:#FFCDD2; border-left: 6px solid #C62828; border-radius: 5px;'>
                            <strong>🚨 Lento:</strong> Han pasado <strong>{dias} días</strong> desde que se abrió la posición hasta la última contratación.<br>
                            <em>Considera ajustar filtros o acelerar las entrevistas.</em>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div style='padding:1em; background-color:#C8E6C9; border-left: 6px solid #2E7D32; border-radius: 5px;'>
                            <strong>✅ Bien:</strong> Contratación en <strong>{dias} días</strong>. Flujo de proceso ágil.<br>
                        </div>
                        """, unsafe_allow_html=True)
                

            with col2:
                st.markdown("### Tiempos por posición")

                posiciones_con_datos = []
                
                for pos in df_filtrado["Posicion"].unique():
                    df_pos = df_filtrado[df_filtrado["Posicion"] == pos]
                
                    # Fecha de apertura: primer día que aparece la posición
                    fecha_apertura = df_pos["Fecha"].min()
                
                    # Fecha de contratación: primera vez que hubo contratados
                    fecha_contratado = df_pos[df_pos["Candidatos contratados"] > 0]["Fecha"].min()
                
                    if pd.isna(fecha_apertura) and pd.isna(fecha_contratado):
                        continue  # ni siquiera agregamos si no hay nada
                    elif pd.isna(fecha_contratado):
                        dias = None  # si no hay contratados, lo dejamos vacío
                    else:
                        dias = (fecha_contratado - fecha_apertura).days
                
                    posiciones_con_datos.append((pos, fecha_apertura.date(), dias))
                
                if posiciones_con_datos:
                    heatmap_df = pd.DataFrame(posiciones_con_datos, columns=["Posición", "Fecha de apertura", "Días transcurridos"])
                    
                    # Formateamos la tabla
                    def color_personalizado(val):
                        if pd.isna(val):
                            return ''
                        else:
                            return color_semaforo(val)
                
                    styled_df = heatmap_df.style.applymap(color_personalizado, subset=["Días transcurridos"])
                    st.dataframe(styled_df, use_container_width=True)
                else:
                    st.info("No hay suficientes datos para calcular los tiempos por posición.")


            col3, col4 = st.columns([1, 2])
            with col3:
                st.markdown("### Flujo de Reclutamiento")
                funnel_data = {
                    "Indeed": df_filtrado.get("Recruitment. Candidatos Indeed", pd.Series([0])).sum(),
                    "RCRM": df_filtrado.get("Recruitment. Candidatos R.CRM", pd.Series([0])).sum(),
                    "Viables": df_filtrado.get("Recruitment. Candidatos Viables", pd.Series([0])).sum(),
                    "Contratados": df_filtrado.get("Candidatos contratados", pd.Series([0])).sum()
                }
                fig2, ax2 = plt.subplots(figsize=(12, 10))
                ax2.barh(list(funnel_data.keys())[::-1], list(funnel_data.values())[::-1], color="#4C72B0")
                ax2.set_title("Embudo de Reclutamiento")
                ax2.set_xlabel("Cantidad de Candidatos")
                st.pyplot(fig2)

            with col4:
                st.markdown("### Carga laboral por reclutador")
            
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
            
                if not resumen_completo.empty:
                    # Creamos las dos columnas
                    col_grafico, col_tabla = st.columns(2)
            
                    with col_grafico:
                        fig, ax = plt.subplots(figsize=(6, 2))
                        colores = [color_por_carga(x) for x in resumen_completo["Posiciones abiertas"]]
                        ax.bar(resumen_completo["Nombre reclutador"], resumen_completo["Posiciones abiertas"], color=colores)
                        ax.set_title("Carga laboral")
                        ax.set_ylabel("Abiertas")
                        plt.xticks(rotation=45)
                        st.pyplot(fig)
            
                    with col_tabla:
                        st.markdown("### Detalle de posiciones abiertas por reclutador")
                        st.dataframe(resumen_completo, use_container_width=True)
                else:
                    st.info("No hay posiciones abiertas actualmente.")

 

        elif pagina == "Evaluación y Conversión":
            st.markdown("### Etapa 1: Captación y evaluación por reclutador")

            col1, col2 = st.columns(2)
            with col1:
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

                fig, ax = plt.subplots(figsize=(12, 8))

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
                plt.tight_layout()

                st.pyplot(fig)

                

            with col2:
                st.markdown("### Descarte por reclutadores")
                etapa2 = {
                    "Hard Skills": df_filtrado.get("Screening. CNV. Perfil no calificado (hard skills)", pd.Series([0])).sum(),
                    "Fuera de presupuesto": df_filtrado.get("Screening. CNV. Fuera de presupuesto", pd.Series([0])).sum(),
                    "Soft Skills": df_filtrado.get("Screening. CNV. Soft Skills", pd.Series([0])).sum(),
                    "Inglés": df_filtrado.get("Screening. CNV. Nivel de ingles", pd.Series([0])).sum(),
                    "No se presentó": df_filtrado.get("Screening. CNV. No se presento / Inpuntual", pd.Series([0])).sum(),
                    "Localidad": df_filtrado.get("Screening. CNV. Localidad", pd.Series([0])).sum()
                }
                etapa2 = {k: v for k, v in etapa2.items() if v > 0}
                if etapa2:
                    fig3, ax3 = plt.subplots(figsize=(3,3))
                    ax3.pie(etapa2.values(), labels=etapa2.keys(), autopct='%1.1f%%', startangle=140, colors=plt.get_cmap('Pastel1').colors)
                    ax3.axis('equal')
                    st.pyplot(fig3)


            col3, col4 = st.columns([1, 1])
            with col3:
                st.markdown("### Conversión de Viables a Contratados")
                by_vacancy = df_filtrado.groupby("Posicion")[["Recruitment. Candidatos nuevos", "Recruitment. Candidatos Viables", "Candidatos contratados"]].sum()
                if not by_vacancy.empty:
                    conversion = (by_vacancy["Candidatos contratados"] / by_vacancy["Recruitment. Candidatos Viables"]).fillna(0) * 100
                    conversion = conversion[conversion > 0]
                    if not conversion.empty:
                        fig5, ax5 = plt.subplots(figsize=(5,5))
                        ax5.barh(conversion.index, conversion.values, color="#C44E52")
                        ax5.set_title("Tasa de Conversión de Viables a Contratados")
                        ax5.set_xlabel("% Conversión")
                        st.pyplot(fig5)

            with col4:
                st.markdown("### Descartes por cliente")
                etapa3 = {
                    "Química": df_filtrado.get("S. Cliente. Quimica personal", pd.Series([0])).sum(),
                    "Inconsistencias": df_filtrado.get("S. Cliente. Inconsistencias en expertise", pd.Series([0])).sum(),
                    "Perfil": df_filtrado.get("S. Cliente. No cumple con el perfil", pd.Series([0])).sum(),
                    "Inglés": df_filtrado.get("S. Cliente. Nivel de ingles", pd.Series([0])).sum(),
                    "Sobrecalificado": df_filtrado.get("S. Cliente. Sobrecalificado", pd.Series([0])).sum()
                }
                etapa3 = {k: v for k, v in etapa3.items() if v > 0}
                if etapa3:
                    fig4, ax4 = plt.subplots(figsize=(5,5))
                    ax4.pie(etapa3.values(), labels=etapa3.keys(), autopct='%1.1f%%', startangle=140, colors=plt.get_cmap('Pastel2').colors)
                    ax4.axis('equal')
                    st.pyplot(fig4) 
    
    except Exception as e:
        st.error(f"Error al cargar o procesar el archivo: {e}")
