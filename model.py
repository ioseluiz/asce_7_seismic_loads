import numpy as np

class SeismicModel:
    """
    Clase encargada de la lógica de negocio y cálculos estructurales
    basados en ASCE 7-05 Capitulos 11 y 12.
    """
    def __init__(self):
        self.results = {}
        
    def interpolate_coeff(self, value, distinct_values, coeffs):
        """Interpolación lineal para coeficientes Fa y Fv."""
        return np.interp(value, distinct_values, coeffs)

    def get_fa(self, site_class, ss):
        """Tabla 11.4-1 ASCE 7-05"""
        ss_vals = [0.25, 0.50, 0.75, 1.00, 1.25]
        
        table = {
            'A': [0.8, 0.8, 0.8, 0.8, 0.8],
            'B': [1.0, 1.0, 1.0, 1.0, 1.0],
            'C': [1.2, 1.2, 1.1, 1.0, 1.0],
            'D': [1.6, 1.4, 1.2, 1.1, 1.0],
            'E': [2.5, 1.7, 1.2, 0.9, 0.9],
            'F': [None] * 5 
        }
        
        if site_class == 'F': return None
        return self.interpolate_coeff(ss, ss_vals, table[site_class])

    def get_fv(self, site_class, s1):
        """Tabla 11.4-2 ASCE 7-05"""
        s1_vals = [0.10, 0.20, 0.30, 0.40, 0.50]
        
        table = {
            'A': [0.8, 0.8, 0.8, 0.8, 0.8],
            'B': [1.0, 1.0, 1.0, 1.0, 1.0],
            'C': [1.7, 1.6, 1.5, 1.4, 1.3],
            'D': [2.4, 2.0, 1.8, 1.6, 1.5],
            'E': [3.5, 3.2, 2.8, 2.4, 2.4],
            'F': [None] * 5
        }
        
        if site_class == 'F': return None
        return self.interpolate_coeff(s1, s1_vals, table[site_class])

    def calculate_loads(self, inputs):
        """
        Realiza el cálculo completo en kN y luego convierte los resultados
        a la unidad solicitada para visualización.
        """
        try:
            # 1. Parámetros de Sitio
            Ss = inputs['Ss']
            S1 = inputs['S1']
            site_class = inputs['SiteClass']
            
            Fa = self.get_fa(site_class, Ss)
            Fv = self.get_fv(site_class, S1)
            
            # Ecuaciones 11.4-1 y 11.4-2
            SMS = Fa * Ss
            SM1 = Fv * S1
            
            # Ecuaciones 11.4-3 y 11.4-4
            SDS = (2/3) * SMS
            SD1 = (2/3) * SM1
            
            # 2. Periodo Fundamental (Sección 12.8.2)
            # Ct en SI (Metros):
            ct_si_map = {
                'Acero (Pórticos Resistentes a Momento)': (0.0724, 0.8),
                'Concreto (Pórticos Resistentes a Momento)': (0.0466, 0.9),
                'Pórticos con Arriostramiento Excéntrico': (0.0731, 0.75),
                'Otros Sistemas': (0.0488, 0.75)
            }
            
            structure_type = inputs['StructureType']
            Ct, x_exp = ct_si_map[structure_type]
            
            stories = inputs['stories'] # W en kN (siempre)
            hn = sum([p['h'] for p in stories])
            
            Ta = Ct * (hn ** x_exp)
            
            # Límites de Periodo
            Cu_table_sd1 = [0.1, 0.15, 0.2, 0.3, 0.4]
            Cu_table_val = [1.7, 1.6, 1.5, 1.4, 1.4]
            Cu = np.interp(SD1, Cu_table_sd1, Cu_table_val)
            if SD1 > 0.4: Cu = 1.4
            
            T_upper = Cu * Ta
            T_used = min(T_upper, Ta)
            
            # 3. Coeficiente Cs
            R = inputs['R']
            Ie = inputs['Ie']
            TL = inputs['TL']
            
            Cs_calc = SDS / (R / Ie)
            
            if T_used <= TL:
                Cs_max = SD1 / (T_used * (R / Ie))
            else:
                Cs_max = (SD1 * TL) / (T_used**2 * (R / Ie))
                
            # Limites Minimos
            Cs_min = 0.01 
            
            # Modificación solicitada: Eq 12.8-5 ajustada (0.044 * SDS, sin Ie)
            Cs_min_2 = 0.044 * SDS 
            
            Cs_min_3 = 0.0
            if S1 >= 0.6:
                Cs_min_3 = (0.5 * S1) / (R / Ie)
                
            Cs = min(Cs_calc, Cs_max)
            # Aplicamos el máximo de los mínimos
            Cs = max(Cs, Cs_min_2, Cs_min_3, Cs_min)
            
            # 4. Cortante Basal (Cálculo interno en kN)
            W_total_kN = sum([p['w'] for p in stories])
            V_kN = Cs * W_total_kN
            
            # 5. Distribución Vertical
            if T_used <= 0.5:
                k = 1.0
            elif T_used >= 2.5:
                k = 2.0
            else:
                k = 1 + ((T_used - 0.5) / 2.0)
            
            temp_h = 0
            story_data_processed = []
            
            # Pre-proceso para cálculos
            for story in stories:
                temp_h += story['h']
                story_data_processed.append({
                    'w_kN': story['w'], # Guardamos valor base
                    'hx': temp_h,
                    'name': story.get('name', f"Nivel {temp_h}")
                })
                
            sum_whk = 0
            for item in story_data_processed:
                sum_whk += item['w_kN'] * (item['hx'] ** k)
            
            # --- CONVERSIÓN DE UNIDADES ---
            # Las entradas siempre son en kN (según view.py)
            unit = inputs.get('unit', 'kN')
            
            # Factores de conversión desde kN
            # 1 kN = 0.10197 Ton
            # 1 kN = 101.97 kg
            factors = {'kN': 1.0, 'Ton': 0.10197, 'kg': 101.97}
            f_conv = factors.get(unit, 1.0)
            
            # Aplicar conversión a resultados globales
            W_total_out = W_total_kN * f_conv
            V_out = V_kN * f_conv
            
            # Calcular fuerzas por piso y aplicar conversión
            fx_list_out = []
            
            for item in story_data_processed:
                cvx = (item['w_kN'] * (item['hx'] ** k)) / sum_whk
                fx_kN = cvx * V_kN
                
                # Valores de salida convertidos
                item['w'] = item['w_kN'] * f_conv
                item['Fx'] = fx_kN * f_conv
                item['Cvx'] = cvx
                fx_list_out.append(item['Fx'])
                
            # Acumular cortante (Vx) con valores convertidos
            accum_shear = 0
            shears_out = [0] * len(fx_list_out)
            for i in range(len(fx_list_out)-1, -1, -1):
                accum_shear += fx_list_out[i]
                shears_out[i] = accum_shear
            
            for i, item in enumerate(story_data_processed):
                item['Vx'] = shears_out[i]

            # 6. Espectro
            T0 = 0.2 * SD1 / SDS
            Ts = SD1 / SDS
            period_range = np.linspace(0, TL + 2, 100)
            sa_values = []
            for t in period_range:
                if t < T0: sa = SDS * (0.4 + 0.6 * (t / T0))
                elif t < Ts: sa = SDS
                elif t < TL: sa = SD1 / t
                else: sa = (SD1 * TL) / (t**2)
                sa_values.append(sa)

            self.results = {
                'Fa': Fa, 'Fv': Fv,
                'SMS': SMS, 'SM1': SM1,
                'SDS': SDS, 'SD1': SD1,
                'Ta': Ta, 'T_used': T_used, 'Cu': Cu,
                'Cs': Cs, 
                'Cs_min_local': Cs_min_2, # Guardar valor min local para reporte
                'W_total': W_total_out, # Convertido
                'V': V_out,             # Convertido
                'k': k,
                'T0': T0, 'Ts': Ts,
                'distribution': story_data_processed, # Convertido
                'spectrum': (period_range, sa_values),
                'inputs': inputs
            }
            return self.results
            
        except Exception as e:
            return {'error': str(e)}

    def generate_markdown_report(self):
        """Genera un reporte formateado en Markdown compatible con PyQt5."""
        if not self.results or 'error' in self.results:
            return "No hay resultados válidos para generar el reporte."
            
        r = self.results
        inp = r['inputs']
        u = inp.get('unit', 'kN')
        
        md = f"""
# Reporte de Cálculo de Cargas Sísmicas (ASCE 7-05)

## 1. Parámetros de Entrada
- **Ss**: {inp['Ss']} g
- **S1**: {inp['S1']} g
- **Clase de Sitio**: {inp['SiteClass']}
- **Factor de Importancia (Ie)**: {inp['Ie']}
- **Coeficiente de Modificación de Respuesta (R)**: {inp['R']}
- **Periodo Largo de Transición (TL)**: {inp['TL']} s
- **Unidad de Resultados**: {u}

## 2. Coeficientes de Sitio (Tablas 11.4-1 y 11.4-2)
- **Fa** = {r['Fa']:.3f}
- **Fv** = {r['Fv']:.3f}

## 3. Parámetros de Aceleración Espectral
**SMS** = Fa × Ss = **{r['SMS']:.3f} g**
**SM1** = Fv × S1 = **{r['SM1']:.3f} g**

Parámetros de diseño (2/3 del sismo máximo considerado):
**SDS** = (2/3) × SMS = **{r['SDS']:.3f} g**
**SD1** = (2/3) × SM1 = **{r['SD1']:.3f} g**

## 4. Periodo Fundamental
**Ta** = Ct × hn^x = **{r['Ta']:.3f} s**
**Cu × Ta** = {r['Cu']:.2f} × {r['Ta']:.3f} = **{r['Cu']*r['Ta']:.3f} s**
**Periodo de Diseño (T)**: {r['T_used']:.3f} s

## 5. Cortante Basal (Sec. 12.8.1)
El coeficiente de respuesta sísmica se calcula considerando:

1.  **Cálculo Base (Ec. 12.8-2):**
    Cs = SDS / (R/Ie) = {r['SDS']:.3f} / ({inp['R']}/{inp['Ie']}) = {r['SDS'] / (inp['R']/inp['Ie']):.4f}

2.  **Mínimo Local (Ec. 12.8-5 Modificada REP-2021):**
    Cs,min = 0.044 × SDS = 0.044 × {r['SDS']:.3f} = {r['Cs_min_local']:.4f}

**Coeficiente de Diseño Final:**
**Cs** = **{r['Cs']:.4f}**

El cortante basal elástico (Ec. 12.8-1) es:
**V** = Cs × W = {r['Cs']:.4f} × {r['W_total']:.2f} = **{r['V']:.2f} {u}**

## 6. Distribución Vertical de Fuerzas (Sec. 12.8.3)
Exponente de distribución **k** = {r['k']:.2f}.

| Nivel | Altura hx (m) | Peso w ({u}) | Cvx | Fx ({u}) | Vx ({u}) |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
        dist = r['distribution'][::-1]
        for d in dist:
            md += f"| {d['name']} | {d['hx']:.2f} | {d['w']:.2f} | {d['Cvx']:.4f} | {d['Fx']:.2f} | {d['Vx']:.2f} |\n"
            
        md += "\n*Nota: Vx es el cortante acumulado en el piso.*"
        return md