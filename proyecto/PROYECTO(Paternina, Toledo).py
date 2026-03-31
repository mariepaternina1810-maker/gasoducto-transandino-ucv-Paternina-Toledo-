import streamlit as st
import pandas as pd

# --- 1. BASE DE DATOS TÉCNICA Y CONSTANTES ---

# Tabla 1: Tuberías de Acero API 5L (Sch 40)
# Clave: Diámetro nominal (pulgadas). Valores: Diámetro ext (mm), Espesor (mm), Costo ($/m)
tuberias = {
    12: {"d_ext_mm": 323.8, "espesor_mm": 10.31, "costo_m": 185},
    16: {"d_ext_mm": 406.4, "espesor_mm": 12.70, "costo_m": 260},
    20: {"d_ext_mm": 508.0, "espesor_mm": 15.09, "costo_m": 350},
    24: {"d_ext_mm": 609.6, "espesor_mm": 17.48, "costo_m": 440}
}

# Tabla 2: Grados de Acero y Resistencia
grados_acero = {
    "X52": {"SMYS": 52000, "F": 0.72},
    "X60": {"SMYS": 60000, "F": 0.72}
}

# Condiciones base del Gasoducto Trans-Andino
LONGITUD_TOTAL_KM = 400
P_INICIAL_PSIA = 800
P_ENTREGA_MIN_PSIA = 500
T_SUCCION_K = 293.15  # 20°C pasados a Kelvin
GAMMA = 0.65
Z = 0.90

import math

# --- 2. FUNCIONES MATEMÁTICAS ---

def calcular_presion_salida(p_in, q, l_km, d_pulgadas, eficiencia=1.0):
    """
    Calcula la presión de salida usando la Ecuación de Weymouth.
    Asumimos una eficiencia (E) de 1.0 por defecto.
    """
    # Extraemos las constantes de nuestro bloque anterior
    gamma = GAMMA
    t_k = T_SUCCION_K
    z = Z
    
    # Término derecho de la ecuación de Weymouth
    # Nota: El profesor Olejnik usa la constante 433.5. 
    termino_friccion = 433.5 * ((q / eficiencia)**2) * ((l_km * gamma * t_k * z) / (d_pulgadas**5.33))
    
    # Despejamos P2 (P_out)
    p_out_cuadrado = (p_in**2) - termino_friccion
    
    # Si la fricción es muy alta, el gas no llega (presión negativa)
    if p_out_cuadrado <= 0:
        return 0.0  # El flujo se detiene
        
    return math.sqrt(p_out_cuadrado)

def calcular_compresor(p_in, p_out, q_mmscfd, t1_k=293.15):
    """
    Calcula la potencia (HP) y la temperatura de descarga (T2) en Kelvin
    para una estación de compresión.
    """
    # Constantes típicas (verifica en tus apuntes si el profe dio valores exactos)
    k = 1.3 # Relación de calores específicos Cp/Cv para gas natural
    r = 10.73 # Constante de los gases (en unidades consistentes con psia y R/K, revisa tu convención)
    eta = 0.75 # Eficiencia del compresor (asumimos 75% si no se especifica)
    z = Z # Nuestro 0.90 de las condiciones base
    
    # Relación de compresión
    rc = p_out / p_in
    exponente = (k - 1) / k
    
    # 1. Calculamos la Temperatura de descarga (T2)
    t2_k = t1_k * (rc ** exponente)
    
    # 2. Calculamos la Potencia (HP)
    # Convertimos Q de MMscfd para la fórmula
    flujo_convertido = (q_mmscfd * (10**6)) / (24 * 3600 * eta)
    hp = flujo_convertido * ((z * r * t1_k) / (k - 1)) * ((rc ** exponente) - 1)
    
    return hp, t2_k

def calcular_tac(l_km, d_pulgadas, hp_total, costo_kwh, tasa_interes_pct, vida_util_anios=20):
    """
    Calcula el Costo Total Anualizado (TAC) = (CAPEX * CRF) + OPEX.
    Retorna también el desglose para poder graficarlo después.
    """
    # 1. CAPEX de la Tubería
    # Obtenemos el costo por metro del diccionario de tuberías
    costo_por_metro = tuberias[d_pulgadas]["costo_m"]
    capex_tuberia = (l_km * 1000) * costo_por_metro # Convertimos los 400 km a metros
    
    # 2. CAPEX de Compresores
    # (Asumimos un costo estándar de 1500 USD por cada HP instalado si el profe no dio un valor específico)
    costo_hp_instalado = 1500 
    capex_compresores = hp_total * costo_hp_instalado
    
    capex_total = capex_tuberia + capex_compresores
    
    # 3. Factor de Recuperación de Capital (CRF)
    i = tasa_interes_pct / 100.0
    n = vida_util_anios
    crf = (i * ((1 + i)**n)) / (((1 + i)**n) - 1)
    
    # 4. OPEX (Costo operativo de energía anual)
    # 1 HP equivale a 0.7457 kW. Asumimos operación continua 24/7 los 365 días del año.
    kw_total = hp_total * 0.7457
    opex_energia = kw_total * 24 * 365 * costo_kwh
    
    # 5. Costo Total Anualizado (TAC)
    tac = (capex_total * crf) + opex_energia
    
    return tac, capex_tuberia, capex_compresores, opex_energia

def verificar_maop(p_max, d_ext_mm, espesor_mm, grado):
    """
    Verifica si la presión supera el límite de Barlow.
    Retorna True si es seguro, False si la tubería explota.
    """
    smys = grados_acero[grado]["SMYS"]
    f = grados_acero[grado]["F"]
    
    # Convertimos mm a pulgadas para la fórmula de Barlow (1 pulgada = 25.4 mm)
    d_ext_pulg = d_ext_mm / 25.4
    espesor_pulg = espesor_mm / 25.4
    
    # Límite de Barlow: P = (2 * Espesor * SMYS * F) / Diámetro Externo
    presion_maxima_permitida = (2 * espesor_pulg * smys * f) / d_ext_pulg
    
    return p_max <= presion_maxima_permitida, presion_maxima_permitida

# 1. Configuración básica de la página (¡siempre va primero!)
st.set_page_config(
    page_title="Gemelo Digital: Gasoducto Trans-Andino",
    page_icon="🏭",
    layout="wide"
)

st.title("🏭 Optimización de Transporte de Gas")
st.subheader("Caso de Estudio: Gasoducto Trans-Andino")
st.markdown("---")

# 2. Panel de Configuración (Sidebar)
with st.sidebar:
    st.header("⚙️ Panel de Configuración")
    
    st.subheader("1. Parámetros Económicos")
    costo_energia = st.number_input("Costo de energía (USD/kWh)", min_value=0.0, value=0.10, step=0.01)
    tasa_interes = st.number_input("Tasa de interés (%)", min_value=0.0, value=10.0, step=0.5)
    
    st.subheader("2. Selección de Material")
    diametro = st.selectbox("Diámetro Comercial (pulgadas) [tomando en cuenta el costo del acero ($/m)]", [12, 16, 20, 24])
    grado_acero = st.selectbox("Grado del Acero", ["X52", "X60"])
    
    st.subheader("3. Variables Operativas")
    flujo_q = st.number_input("Flujo de gas (MMscfd)", min_value=100.0, value=500.0, step=50.0)
    n_estaciones = st.number_input("Número de estaciones de compresión (N)", min_value=0, value=3, step=1)
    
    st.markdown("---")
    simular = st.button("🚀 Ejecutar Simulación", type="primary")

# 3. Visualización Principal (Main Panel)
st.header("📊 Dashboard de Resultados")

import plotly.graph_objects as go
import plotly.express as px

# Columnas vacías iniciales para las métricas principales
col1, col2, col3 = st.columns(3)
metrica_tac = col1.empty()
metrica_hp = col2.empty()
metrica_presion = col3.empty()

# Dejamos las métricas en cero antes de simular
metrica_tac.metric(label="Costo Total Anualizado (TAC)", value="$ 0.00")
metrica_hp.metric(label="Potencia Total Instalada", value="0 HP")
metrica_presion.metric(label="Presión Final de Entrega", value="0 psia")

st.markdown("---")
tab1, tab2 = st.tabs(["📈 Perfil Hidráulico", "💰 Desglose de Costos"])
espacio_grafico_1 = tab1.empty()
espacio_grafico_2 = tab2.empty()

st.markdown("---")
st.header("⚠️ Sistema de Seguridad")
espacio_alertas = st.empty()

# --- AQUÍ OCURRE LA MAGIA CUANDO PRESIONAS EL BOTÓN ---
if simular:
    with st.spinner("Simulando Gasoducto Trans-Andino..."):
        # 1. Dividimos el gasoducto en tramos
        segmentos = n_estaciones + 1
        l_segmento = LONGITUD_TOTAL_KM / segmentos
        
        distancias = [0]
        presiones = [P_INICIAL_PSIA]
        
        p_actual = P_INICIAL_PSIA
        hp_total = 0
        t_max_k = T_SUCCION_K
        p_max_sistema = P_INICIAL_PSIA
        
        for i in range(segmentos):
            # Caída de presión en el tramo por fricción
            p_llegada = calcular_presion_salida(p_actual, flujo_q, l_segmento, diametro)
            distancias.append(distancias[-1] + l_segmento)
            presiones.append(p_llegada)

            # --- ¡NUEVO! ---
            # Si la presión cae a 0, detenemos todo para evitar la división por cero
            if p_llegada <= 0:
                with espacio_alertas.container():
                    st.error(f"❌ ERROR FÍSICO: La presión cayó a 0 psia antes de llegar a la estación {i+1} (km {distancias[-1]:.0f}). ¡El gas no llega!")
                    st.info("💡 Tip de diseño: Intenta aumentar el diámetro de la tubería o agregar más estaciones de compresión.")
                st.stop() # Esto detiene la ejecución del código justo aquí
            # --------------
            
            # Si hay estación de compresión (y no es el final del tubo)
            if i < n_estaciones:
                # El compresor vuelve a subir la presión a los 800 psia iniciales
                p_salida_compresor = P_INICIAL_PSIA 
                hp, t2 = calcular_compresor(p_llegada, p_salida_compresor, flujo_q)
                
                hp_total += hp
                t_max_k = max(t_max_k, t2)
                
                # Para el gráfico: la presión sube instantáneamente en el mismo kilómetro
                distancias.append(distancias[-1])
                presiones.append(p_salida_compresor)
                
                p_actual = p_salida_compresor
                p_max_sistema = max(p_max_sistema, p_salida_compresor)
            else:
                p_actual = p_llegada # Esta es la presión final de entrega
        
        # 2. Cálculos Económicos
        tac, capex_tub, capex_comp, opex = calcular_tac(LONGITUD_TOTAL_KM, diametro, hp_total, costo_energia, tasa_interes)
        
        # 3. Actualizamos el Dashboard superior
        metrica_tac.metric(label="Costo Total Anualizado (TAC)", value=f"$ {tac:,.2f}")
        metrica_hp.metric(label="Potencia Total Instalada", value=f"{hp_total:,.0f} HP")
        
        delta_p = p_actual - P_ENTREGA_MIN_PSIA
        delta_color = "normal" if delta_p >= 0 else "inverse"
        metrica_presion.metric(label="Presión Final", value=f"{p_actual:.1f} psia", delta=f"{delta_p:.1f} psia", delta_color=delta_color)
        
        # 4. Dibujamos los gráficos interactivos
        with espacio_grafico_1:
            fig_presion = go.Figure()
            fig_presion.add_trace(go.Scatter(x=distancias, y=presiones, mode='lines+markers', name='Perfil de Presión', line=dict(color='#ff4b4b', width=3)))
            # Línea punteada marcando el mínimo exigido
            fig_presion.add_hline(y=P_ENTREGA_MIN_PSIA, line_dash="dash", line_color="#0068c9", annotation_text="Mínimo 500 psia")
            fig_presion.update_layout(xaxis_title="Distancia (km)", yaxis_title="Presión (psia)", height=400)
            st.plotly_chart(fig_presion, use_container_width=True)
            
        with espacio_grafico_2:
            datos_costos = pd.DataFrame({
                "Categoría": ["CAPEX Ducto", "CAPEX Compresores", "OPEX Energía (Anual)"],
                "Costo ($)": [capex_tub, capex_comp, opex]
            })
            fig_costos = px.pie(datos_costos, values="Costo ($)", names="Categoría", hole=0.4, color_discrete_sequence=['#ff4b4b', '#0068c9', '#09ab3b'])
            st.plotly_chart(fig_costos, use_container_width=True)
            
        # 5. Imprimimos el Sistema de Alertas
        with espacio_alertas.container():
            d_ext = tuberias[diametro]["d_ext_mm"]
            espesor = tuberias[diametro]["espesor_mm"]
            
            # Verificación 1: Límite de Barlow
            es_seguro_maop, p_limite = verificar_maop(p_max_sistema, d_ext, espesor, grado_acero)
            if es_seguro_maop:
                st.success(f"✅ MAOP: La presión ({p_max_sistema:.1f} psia) cumple el límite de Barlow ({p_limite:.1f} psia).")
            else:
                st.error(f"❌ ALERTA MAOP: La presión ({p_max_sistema:.1f} psia) SUPERA el límite de Barlow ({p_limite:.1f} psia). El tubo puede colapsar.")
            
            # Verificación 2: Límite Térmico
            t_max_c = t_max_k - 273.15
            if t_max_c <= 65:
                st.success(f"✅ Térmica: Temperatura máxima ({t_max_c:.1f} °C) segura.")
            else:
                st.error(f"❌ ALERTA TÉRMICA: La temperatura tras comprimir ({t_max_c:.1f} °C) supera los 65 °C requeridos.")
            
            # Verificación 3: Cumplimiento de Entrega
            if p_actual >= P_ENTREGA_MIN_PSIA:
                st.success(f"✅ Entrega: Presión final de {p_actual:.1f} psia (cumple con el mínimo de 500 psia).")
            else:
                st.error(f"❌ ALERTA DE ENTREGA: El gas no llega con fuerza suficiente ({p_actual:.1f} psia). Necesitas más diámetro o más estaciones.")
