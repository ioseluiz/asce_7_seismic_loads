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
        
    def export_spectrum_to_csv(self, filename):
        """
        Exporta los datos del espectro (Periodo vs Sa) a un archivo
        """

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
        """
        Genera un reporte en formato HTML rico, compatible con QTextEdit,
        usando subíndices y formato legible en lugar de LaTeX crudo.
        """
        if not self.results or 'error' in self.results:
            return "<h3>No hay resultados válidos para generar el reporte.</h3>"
            
        r = self.results
        inp = r['inputs']
        u = inp.get('unit', 'kN')
        R_Ie = inp['R'] / inp['Ie']
        
        # Estilos básicos para las tablas HTML
        table_style = 'border-collapse: collapse; width: 100%; border: 1px solid #dddddd;'
        th_style = 'background-color: #f2f2f2; border: 1px solid #dddddd; padding: 8px; text-align: left;'
        td_style = 'border: 1px solid #dddddd; padding: 8px;'
        
        # Construcción del HTML
        html = f"""
        <h1 style="color: #2c3e50;">Memoria de Cálculo Sísmico (ASCE 7-05)</h1>
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
        <p>Interpolación de tablas (ASCE 11.4):</p>
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
        <p>Puntos de control de la curva (T<sub>0</sub>, T<sub>S</sub>, T<sub>L</sub>):</p>
        <ul>
            <li><b>T<sub>0</sub></b> = 0.2 · (S<sub>D1</sub> / S<sub>DS</sub>) = <b>{r['T0']:.4f} s</b></li>
            <li><b>T<sub>S</sub></b> = S<sub>D1</sub> / S<sub>DS</sub> = <b>{r['Ts']:.4f} s</b></li>
            <li><b>T<sub>L</sub></b> = <b>{inp['TL']:.1f} s</b></li>
        </ul>
        
        <p><b>Ecuaciones por tramos:</b></p>
        <ul>
            <li><i style="color:gray">T &lt; T<sub>0</sub> :</i> &nbsp; S<sub>a</sub> = S<sub>DS</sub> · (0.4 + 0.6 · T / T<sub>0</sub>)</li>
            <li><i style="color:gray">T<sub>0</sub> &le; T &le; T<sub>S</sub> :</i> &nbsp; S<sub>a</sub> = <b>{r['SDS']:.3f} g</b> (Meseta)</li>
            <li><i style="color:gray">T<sub>S</sub> &lt; T &le; T<sub>L</sub> :</i> &nbsp; S<sub>a</sub> = {r['SD1']:.3f} / T</li>
            <li><i style="color:gray">T &gt; T<sub>L</sub> :</i> &nbsp; S<sub>a</sub> = ({r['SD1']:.3f} · {inp['TL']:.1f}) / T<sup>2</sup></li>
        </ul>

        <h2 style="color: #34495e;">4. Periodo Fundamental (T)</h2>
        <p>
        Altura Total h<sub>n</sub> = {sum(s['h'] for s in inp['stories']):.2f} m<br>
        Periodo aproximado <b>T<sub>a</sub></b> = {r['Ta']:.4f} s<br>
        Límite Superior <b>C<sub>u</sub>·T<sub>a</sub></b> = {r['Cu']:.3f} · {r['Ta']:.4f} = {r['Cu']*r['Ta']:.4f} s
        </p>
        <p style="background-color: #e8f8f5; padding: 10px; border-left: 5px solid #1abc9c;">
        <b>Periodo de Diseño T = {r['T_used']:.4f} s</b>
        </p>

        <h2 style="color: #34495e;">5. Cortante Basal (V)</h2>
        <p>Coeficiente Sísmico C<sub>s</sub>:</p>
        <ul>
            <li>Base: S<sub>DS</sub> / (R/I<sub>e</sub>) = <b>{r['SDS']/R_Ie:.5f}</b></li>
            <li>Máximo: S<sub>D1</sub> / (T · R/I<sub>e</sub>) = <b>{r['SD1']/(r['T_used']*R_Ie):.5f}</b></li>
            <li>Mínimo: 0.044 · S<sub>DS</sub> = <b>{r['Cs_min_local']:.5f}</b></li>
        </ul>
        <p><b>C<sub>s</sub> de Diseño = {r['Cs']:.5f}</b></p>
        <p><b>Cortante V</b> = C<sub>s</sub> · W = {r['Cs']:.5f} · {r['W_total']:.2f}<br>
        <span style="font-size: 14pt; font-weight: bold; color: #c0392b;">V = {r['V']:.2f} {u}</span>
        </p>

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