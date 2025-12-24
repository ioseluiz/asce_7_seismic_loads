import numpy as np
import csv

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
    

    def get_sdc(self, sds, sd1, ie):
        """
        Determina la Categoría de Diseño Sísmico (SDC) A-F
        basado en Tablas 11.6-1 y 11.6-2 de ASCE 7-05.
        Se infiere la Categoría de Ocupación mediante Ie.
        """
        # 1. Inferir Occupancy Category (aprox)
        if ie < 1.25: occ_cat = 1 # I o II
        elif ie < 1.5: occ_cat = 3 # III
        else: occ_cat = 4 # IV
        
        # Función auxiliar CORREGIDA (Sin el argumento que causaba error)
        def check_table(val, limits):
            # limits: [0.167, 0.33, 0.50]
            idx = 0
            if val < limits[0]: idx = 0
            elif val < limits[1]: idx = 1
            elif val < limits[2]: idx = 2
            else: idx = 3
            
            # Lógica directa ASCE 7-05
            # 0: <0.167 (A)
            # 1: <0.33 (B, o C si es cat IV)
            # 2: <0.50 (C, o D si es cat IV)
            # 3: >=0.50 (D)
            
            if idx == 0: return 'A'
            if idx == 1: return 'C' if occ_cat == 4 else 'B'
            if idx == 2: return 'D' if occ_cat == 4 else 'C'
            return 'D'

        # SDS Check
        sdc_sds = check_table(sds, [0.167, 0.33, 0.50])
        
        # SD1 Check
        sdc_sd1 = check_table(sd1, [0.067, 0.133, 0.20])
        
        # Tomamos el más severo (Orden alfabético inverso A < B < C < D)
        if sdc_sds > sdc_sd1: return sdc_sds
        return sdc_sd1

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

            # Recuperar Inputs Nuevos
            Omega0 = inputs.get('Omega0', 3.0)
            Rho = inputs.get('Rho', 1.0)
            
            Fa = self.get_fa(site_class, Ss)
            Fv = self.get_fv(site_class, S1)
            
            if Fa is None or Fv is None:
                return {'error': "Clase de sitio F requiere estudio específico."}

            # Ecuaciones 11.4-1 y 11.4-2
            SMS = Fa * Ss
            SM1 = Fv * S1
            
            # Ecuaciones 11.4-3 y 11.4-4
            SDS = (2/3) * SMS
            SD1 = (2/3) * SM1

            SDC = self.get_sdc(SDS, SD1, inputs['Ie'])
            
            # 2. Periodo Fundamental (Sección 12.8.2)
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
            
            if R == 0: R = 1.0 # Evitar div/0
            
            Cs_calc = SDS / (R / Ie)
            
            if T_used <= TL:
                Cs_max = SD1 / (T_used * (R / Ie))
            else:
                Cs_max = (SD1 * TL) / (T_used**2 * (R / Ie))
                
            # Limites Minimos
            Cs_min = 0.01 
            Cs_min_2 = 0.044 * SDS * Ie # Nota: Eq 12.8-5 incluye Ie
            if Cs_min_2 < 0.01: Cs_min_2 = 0.01
            
            Cs_min_3 = 0.0
            if S1 >= 0.6:
                Cs_min_3 = (0.5 * S1) / (R / Ie)
                
            Cs = min(Cs_calc, Cs_max)
            # Aplicamos el máximo de los mínimos
            Cs = max(Cs, Cs_min_2, Cs_min_3, Cs_min)

            # NUEVO: Cálculo de Efectos de Carga (Sección 12.4)
            # Ev = 0.2 * Sds * D
            Ev_coef = 0.2 * SDS
            
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
                    'name': story.get('name', f"Nivel {temp_h:.1f}")
                })
                
            sum_whk = 0
            for item in story_data_processed:
                sum_whk += item['w_kN'] * (item['hx'] ** k)
            
            # --- CONVERSIÓN DE UNIDADES ---
            unit = inputs.get('unit', 'kN')
            factors = {'kN': 1.0, 'Ton': 0.10197, 'kg': 101.97}
            f_conv = factors.get(unit, 1.0)
            
            # Aplicar conversión a resultados globales
            W_total_out = W_total_kN * f_conv
            V_out = V_kN * f_conv
            
            # Calcular fuerzas por piso y aplicar conversión
            fx_list_out = []
            
            if sum_whk == 0:
                for item in story_data_processed:
                    item['w'] = 0; item['Fx'] = 0; item['Cvx'] = 0; item['Vx'] = 0
            else:
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
            T0 = 0.2 * SD1 / SDS if SDS > 0 else 0
            Ts = SD1 / SDS if SDS > 0 else 0
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
                'Cs_min_local': Cs_min_2,
                'W_total': W_total_out, 
                'V': V_out,             
                'k': k,
                'T0': T0, 'Ts': Ts,
                'distribution': story_data_processed, 
                'spectrum': (period_range, sa_values),
                'inputs': inputs,
                'SDC': SDC,
                'Omega0': Omega0,
                'Rho': Rho,
                'Ev_coef': Ev_coef
            }

            return self.results
            
        except Exception as e:
            print(f"Error en calculo: {e}")
            return {'error': str(e)}
        
    def export_spectrum_to_csv(self, filename):
        """Exporta los datos del espectro a CSV"""
        if not self.results or 'spectrum' not in self.results:
            return False, "No hay datos de espectro para exportar."
        
        try:
            periods, sas = self.results['spectrum']
            with open(filename, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Periodo (s)', 'Aceleracion (g)'])
                for t, sa in zip(periods, sas):
                    writer.writerow([f"{t:.4f}", f"{sa:.4f}"])
            return True, "Archivo exportado exitosamente."
        except Exception as e:
            return False, f"Error al escribir archivo: {str(e)}"

    def generate_html_report(self):
        """Genera el reporte HTML completo con combinaciones de carga."""
        if not self.results or 'error' in self.results:
            return "<h3>No hay resultados válidos para generar el reporte.</h3>"
            
        r = self.results
        inp = r['inputs']
        u = inp.get('unit', 'kN')

        # Variables para combinaciones
        Ev = r.get('Ev_coef', 0)
        Rho = r.get('Rho', 1.0)
        Om = r.get('Omega0', 3.0)
        
        # Factores para Combos (D y E)
        comb_5_D = 1.2 + Ev
        comb_7_D = 0.9 - Ev

        R_Ie = inp['R'] / inp['Ie']
        
        # Estilos CSS Inline
        table_style = 'border-collapse: collapse; width: 100%; border: 1px solid #dddddd;'
        th_style = 'background-color: #f2f2f2; border: 1px solid #dddddd; padding: 8px; text-align: left;'
        td_style = 'border: 1px solid #dddddd; padding: 8px;'
        
        # HTML Completo
        html = f"""
        <h1 style="color: #2c3e50;">Memoria de Cálculo Sísmico (ASCE 7-05 / REP-2021)</h1>
        <hr>

        <h2 style="color: #34495e;">1. Parámetros de Diseño</h2>
        <table style="{table_style}">
          <tr><th style="{th_style}">Parámetro</th><th style="{th_style}">Valor</th><th style="{th_style}">Descripción</th></tr>
          <tr><td style="{td_style}"><b>S<sub>s</sub></b></td><td style="{td_style}">{inp['Ss']:.3f} g</td><td style="{td_style}">Aceleración MCER (0.2s)</td></tr>
          <tr><td style="{td_style}"><b>S<sub>1</sub></b></td><td style="{td_style}">{inp['S1']:.3f} g</td><td style="{td_style}">Aceleración MCER (1.0s)</td></tr>
          <tr><td style="{td_style}"><b>Clase Sitio</b></td><td style="{td_style}">{inp['SiteClass']}</td><td style="{td_style}">Perfil de Suelo</td></tr>
          <tr><td style="{td_style}"><b>T<sub>L</sub></b></td><td style="{td_style}">{inp['TL']:.1f} s</td><td style="{td_style}">Periodo Largo Transición</td></tr>
          <tr><td style="{td_style}"><b>I<sub>e</sub></b></td><td style="{td_style}">{inp['Ie']:.2f}</td><td style="{td_style}">Importancia</td></tr>
          <tr><td style="{td_style}"><b>R</b></td><td style="{td_style}">{inp['R']:.1f}</td><td style="{td_style}">Modificación Respuesta</td></tr>
        </table>

        <h2 style="color: #34495e;">2. Coeficientes y Aceleraciones</h2>
        <p>Interpolación de tablas 11.4(ASCE 7-05):</p>
        <ul>
            <li><b>F<sub>a</sub></b> = {r['Fa']:.3f}</li>
            <li><b>F<sub>v</sub></b> = {r['Fv']:.3f}</li>
        </ul>
        <p><b>Sismo Máximo (MCE):</b></p>
        <blockquote>
            S<sub>MS</sub> = F<sub>a</sub> · S<sub>s</sub> = {r['Fa']:.3f} · {inp['Ss']:.3f} = <b>{r['SMS']:.3f} g</b><br>
            S<sub>M1</sub> = F<sub>v</sub> · S<sub>1</sub> = {r['Fv']:.3f} · {inp['S1']:.3f} = <b>{r['SM1']:.3f} g</b>
        </blockquote>
        <p><b>Sismo de Diseño (2/3 MCE):</b></p>
        <blockquote>
            S<sub>DS</sub> = (2/3) · S<sub>MS</sub> = <b>{r['SDS']:.3f} g</b><br>
            S<sub>D1</sub> = (2/3) · S<sub>M1</sub> = <b>{r['SD1']:.3f} g</b>
        </blockquote>

        <h2 style="color: #34495e;">3. Definición del Espectro</h2>
        <p>Puntos de control (T<sub>0</sub>, T<sub>S</sub>, T<sub>L</sub>):</p>
        <ul>
            <li>T<sub>0</sub> = <b>{r['T0']:.4f} s</b></li>
            <li>T<sub>S</sub> = <b>{r['Ts']:.4f} s</b></li>
            <li>T<sub>L</sub> = <b>{inp['TL']:.1f} s</b></li>
        </ul>

        <h2 style="color: #34495e;">4. Periodo y Cortante Basal</h2>
        <p>
        Periodo Aproximado T<sub>a</sub> = {r['Ta']:.4f} s<br>
        <b>Periodo Diseño T = {r['T_used']:.4f} s</b>
        </p>
        <p><b>Coeficiente Sísmico Cs = {r['Cs']:.5f}</b></p>
        <p>Peso Sísmico W = {r['W_total']:.2f} {u}</p>
        <p style="font-size: 14pt; font-weight: bold; color: #c0392b;">Cortante Basal V = {r['V']:.2f} {u}</p>

        <h2 style="color: #34495e;">5. Parámetros Avanzados y Combinaciones</h2>
        <table style="{table_style}">
          <tr><td style="{td_style}"><b>Categoría de Diseño (SDC)</b></td><td style="{td_style}"><b>{r['SDC']}</b></td></tr>
          <tr><td style="{td_style}"><b>Redundancia (&rho;)</b></td><td style="{td_style}">{Rho:.1f}</td></tr>
          <tr><td style="{td_style}"><b>Sobreresistencia (&Omega;<sub>0</sub>)</b></td><td style="{td_style}">{Om:.1f}</td></tr>
        </table>
        
        <h3 style="color: #2c3e50;">Efectos de Carga Sísmica (Sección 12.4)</h3>
        <p>
        <b>Efecto Vertical:</b> E<sub>v</sub> = 0.2 · S<sub>DS</sub> · D = <b>{Ev:.3f} · D</b><br>
        <b>Efecto Horizontal:</b> E<sub>h</sub> = &rho; · Q<sub>E</sub> = <b>{Rho:.1f} · Q<sub>E</sub></b>
        </p>
        
        <h3 style="color: #2c3e50;">Factores para Combinaciones de Carga (LRFD)</h3>
        <p><i>Sustituyendo E = E<sub>h</sub> + E<sub>v</sub> en las combinaciones básicas:</i></p>
        
        <table style="{table_style}">
            <tr style="background-color: #eaf2f8;">
                <th style="{td_style}">Comb. Básica</th>
                <th style="{td_style}">Ecuación Expandida (Uso en Software)</th>
            </tr>
            <tr>
                <td style="{td_style}">1.2D + 1.0E + L</td>
                <td style="{td_style}">
                    <b>({comb_5_D:.3f}) D</b> + <b>{Rho:.1f} Q<sub>E</sub></b> + 1.0 L
                </td>
            </tr>
            <tr>
                <td style="{td_style}">0.9D + 1.0E</td>
                <td style="{td_style}">
                    <b>({comb_7_D:.3f}) D</b> + <b>{Rho:.1f} Q<sub>E</sub></b>
                </td>
            </tr>
        </table>
        
        <h3 style="color: #c0392b;">Combinaciones con Sobreresistencia (&Omega;<sub>0</sub>)</h3>
        <table style="{table_style}">
            <tr>
                <td style="{td_style}">1.2D + 1.0E<sub>m</sub> + L</td>
                <td style="{td_style}">
                    <b>({comb_5_D:.3f}) D</b> + <b>{Om:.1f} Q<sub>E</sub></b> + 1.0 L
                </td>
            </tr>
            <tr>
                <td style="{td_style}">0.9D + 1.0E<sub>m</sub></td>
                <td style="{td_style}">
                    <b>({comb_7_D:.3f}) D</b> + <b>{Om:.1f} Q<sub>E</sub></b>
                </td>
            </tr>
        </table>

        <h2 style="color: #34495e;">6. Distribución Vertical (F<sub>x</sub>)</h2>
        <p>Exponente k = {r['k']:.2f}</p>
        <table style="{table_style}">
          <tr style="background-color: #f2f2f2;">
            <th style="{td_style}">Nivel</th>
            <th style="{td_style}">h<sub>x</sub> (m)</th>
            <th style="{td_style}">w<sub>x</sub> ({u})</th>
            <th style="{td_style}">C<sub>vx</sub></th>
            <th style="{td_style}">F<sub>x</sub> ({u})</th>
            <th style="{td_style}">V<sub>x</sub> ({u})</th>
          </tr>
        """
        
        # Filas de la tabla
        dist = r['distribution'][::-1]
        for d in dist:
            html += f"""
            <tr>
                <td style="{td_style}">{d['name']}</td>
                <td style="{td_style}">{d['hx']:.2f}</td>
                <td style="{td_style}">{d['w']:.2f}</td>
                <td style="{td_style}">{d['Cvx']:.4f}</td>
                <td style="{td_style}"><b>{d['Fx']:.2f}</b></td>
                <td style="{td_style}">{d['Vx']:.2f}</td>
            </tr>
            """
            
        html += "</table>"
        return html