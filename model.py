import numpy as np
import csv

class SeismicModel:
    """
    Clase encargada de la lógica de negocio y cálculos estructurales
    basados en ASCE 7-05 Capitulos 11 y 12.
    Actualizado para mostrar el cálculo explícito de k en el reporte.
    """
    def __init__(self):
        self.results = {}
        
    def interpolate_coeff(self, value, distinct_values, coeffs):
        return np.interp(value, distinct_values, coeffs)

    def get_fa(self, site_class, ss):
        # Referencia: ASCE 7-05 Table 11.4-1
        ss_vals = [0.25, 0.50, 0.75, 1.00, 1.25]
        table = {
            'A': [0.8, 0.8, 0.8, 0.8, 0.8], 'B': [1.0, 1.0, 1.0, 1.0, 1.0],
            'C': [1.2, 1.2, 1.1, 1.0, 1.0], 'D': [1.6, 1.4, 1.2, 1.1, 1.0],
            'E': [2.5, 1.7, 1.2, 0.9, 0.9], 'F': [None] * 5 
        }
        if site_class == 'F': return None
        return self.interpolate_coeff(ss, ss_vals, table[site_class])

    def get_fv(self, site_class, s1):
        # Referencia: ASCE 7-05 Table 11.4-2
        s1_vals = [0.10, 0.20, 0.30, 0.40, 0.50]
        table = {
            'A': [0.8, 0.8, 0.8, 0.8, 0.8], 'B': [1.0, 1.0, 1.0, 1.0, 1.0],
            'C': [1.7, 1.6, 1.5, 1.4, 1.3], 'D': [2.4, 2.0, 1.8, 1.6, 1.5],
            'E': [3.5, 3.2, 2.8, 2.4, 2.4], 'F': [None] * 5
        }
        if site_class == 'F': return None
        return self.interpolate_coeff(s1, s1_vals, table[site_class])

    def get_sdc(self, sds, sd1, ie):
        # Referencia: ASCE 7-05 Tables 11.6-1 y 11.6-2
        if ie < 1.25: occ_cat = 1 
        elif ie < 1.5: occ_cat = 3
        else: occ_cat = 4
        
        def check_table(val, limits):
            idx = 0
            if val < limits[0]: idx = 0
            elif val < limits[1]: idx = 1
            elif val < limits[2]: idx = 2
            else: idx = 3
            if idx == 0: return 'A'
            if idx == 1: return 'C' if occ_cat == 4 else 'B'
            if idx == 2: return 'D' if occ_cat == 4 else 'C'
            return 'D'

        sdc_sds = check_table(sds, [0.167, 0.33, 0.50])
        sdc_sd1 = check_table(sd1, [0.067, 0.133, 0.20])
        return max(sdc_sds, sdc_sd1)

    def get_drift_limit_ratio(self, ie, sdc, structure_type, rho):
        """
        Calcula el coeficiente de deriva admisible (Delta_a/h) según Tabla 12.12-1
        e incluye la penalización de ASCE 7-05 12.12.1.1.
        """
        # Categoría de Ocupación según Ie
        if ie < 1.25: cat = "I/II"
        elif ie < 1.5: cat = "III"
        else: cat = "IV"

        # ASCE 7-05 Tabla 12.12-1
        if cat == "I/II": base_ratio = 0.025
        elif cat == "III": base_ratio = 0.020
        else: base_ratio = 0.015 # IV
            
        is_moment_frame = "Momento" in structure_type
        is_high_seismic = sdc in ['D', 'E', 'F']
        
        note = f"(Tabla 12.12-1, Cat {cat})"
        final_ratio = base_ratio
        
        # ASCE 7-05 12.12.1.1
        if is_moment_frame and is_high_seismic:
            final_ratio = base_ratio / rho
            note += f"<br><i>Reducido por &rho;={rho} (Sección 12.12.1.1)</i>"
            
        return final_ratio, note

    def calculate_loads(self, inputs):
        try:
            Ss = inputs['Ss']; S1 = inputs['S1']; site_class = inputs['SiteClass']
            Omega0 = inputs.get('Omega0', 3.0); Rho = inputs.get('Rho', 1.0)
            
            Fa = self.get_fa(site_class, Ss)
            Fv = self.get_fv(site_class, S1)
            if Fa is None or Fv is None: return {'error': "Sitio F requiere estudio específico."}

            SMS = Fa * Ss; SM1 = Fv * S1
            SDS = (2/3) * SMS; SD1 = (2/3) * SM1
            SDC = self.get_sdc(SDS, SD1, inputs['Ie'])
            
            # Periodo Fundamental Ta (ASCE 7-05 12.8.2.1)
            ct_map = {
                'Acero (Pórticos Resistentes a Momento)': (0.0724, 0.8),
                'Concreto (Pórticos Resistentes a Momento)': (0.0466, 0.9),
                'Pórticos con Arriostramiento Excéntrico': (0.0731, 0.75),
                'Otros Sistemas': (0.0488, 0.75)
            }
            Ct, x_exp = ct_map[inputs['StructureType']]
            stories = inputs['stories']
            hn = sum([p['h'] for p in stories])
            Ta = Ct * (hn ** x_exp)
            
            # Periodo Superior Cu*Ta (Tabla 12.8-1)
            Cu_val = np.interp(SD1, [0.1, 0.15, 0.2, 0.3, 0.4], [1.7, 1.6, 1.5, 1.4, 1.4])
            if SD1 > 0.4: Cu_val = 1.4
            T_upper = Cu_val * Ta
            T_used = min(T_upper, Ta)
            
            R = inputs['R']; Ie = inputs['Ie']; TL = inputs['TL']
            if R == 0: R = 1.0
            
            # Coeficiente Sísmico Cs (Sección 12.8.1.1)
            Cs_calc = SDS / (R / Ie)
            
            # Cs Max (Ec. 12.8-3 o 12.8-4)
            if T_used <= TL: Cs_max = SD1 / (T_used * (R / Ie))
            else: Cs_max = (SD1 * TL) / (T_used**2 * (R / Ie))
                
            # Cs Min (Ec. 12.8-5)
            Cs_min = 0.01 
            Cs_min_2 = 0.044 * SDS * Ie # (Ec. 12.8-5)
            if Cs_min_2 < 0.01: Cs_min_2 = 0.01
            
            # Cs Min Zona Alta (Ec. 12.8-6)
            Cs_min_3 = (0.5 * S1) / (R / Ie) if S1 >= 0.6 else 0.0
            
            Cs = max(min(Cs_calc, Cs_max), Cs_min_2, Cs_min_3, Cs_min)

            Ev_coef = 0.2 * SDS
            W_total_kN = sum([p['w'] for p in stories])
            V_kN = Cs * W_total_kN # Cortante Basal (Ec. 12.8-1)
            
            # Exponente k (Sección 12.8.3)
            if T_used <= 0.5: k = 1.0
            elif T_used >= 2.5: k = 2.0
            else: k = 1 + ((T_used - 0.5) / 2.0)
            
            # Cálculos de Derivas y Distribución
            drift_ratio, drift_note = self.get_drift_limit_ratio(Ie, SDC, inputs['StructureType'], Rho)
            
            temp_h = 0; story_data = []
            for story in stories:
                temp_h += story['h']
                da_val = story['h'] * drift_ratio 
                story_data.append({
                    'w_kN': story['w'], 
                    'hx': temp_h, 
                    'h_story': story['h'], 
                    'delta_a': da_val,     
                    'name': story.get('name', f"Nivel {temp_h:.1f}")
                })
                
            sum_whk = sum([item['w_kN'] * (item['hx'] ** k) for item in story_data])
            
            unit = inputs.get('unit', 'kN')
            f_conv = {'kN': 1.0, 'Ton': 0.10197, 'kg': 101.97}.get(unit, 1.0)
            len_unit = "cm"
            f_len = 100.0 # m a cm
            
            W_total_out = W_total_kN * f_conv; V_out = V_kN * f_conv
            fx_list_out = []
            
            if sum_whk > 0:
                for item in story_data:
                    # Cvx (Ec. 12.8-12)
                    cvx = (item['w_kN'] * (item['hx'] ** k)) / sum_whk
                    # Fx (Ec. 12.8-11)
                    fx_kN = cvx * V_kN
                    item.update({
                        'w': item['w_kN']*f_conv, 
                        'Fx': fx_kN*f_conv, 
                        'Cvx': cvx,
                        'Da_disp': item['delta_a'] * f_len
                    })
                    fx_list_out.append(item['Fx'])
                
                accum = 0; shears = []
                for f in reversed(fx_list_out): accum += f; shears.insert(0, accum)
                for i, item in enumerate(story_data): item['Vx'] = shears[i]
            
            # Espectro de Diseño (Sección 11.4.5)
            T0 = 0.2 * SD1 / SDS if SDS > 0 else 0
            Ts = SD1 / SDS if SDS > 0 else 0
            p_range = np.linspace(0, TL + 2, 100)
            sa_vals = []
            for t in p_range:
                if t < T0: sa = SDS * (0.4 + 0.6 * (t / T0))
                elif t < Ts: sa = SDS
                elif t < TL: sa = SD1 / t
                else: sa = (SD1 * TL) / (t**2)
                sa_vals.append(sa)

            self.results = {
                'Fa': Fa, 'Fv': Fv, 'SMS': SMS, 'SM1': SM1, 'SDS': SDS, 'SD1': SD1,
                'Ta': Ta, 'T_used': T_used, 'Cu': Cu_val, 'Cs': Cs, 'Cs_calc': Cs_calc,
                'Cs_max': Cs_max, 'Cs_min': Cs_min_2, 'k': k,
                'W_total': W_total_out, 'V': V_out, 
                'T0': T0, 'Ts': Ts,
                'distribution': story_data, 'spectrum': (p_range, sa_vals),
                'inputs': inputs, 'SDC': SDC, 'Omega0': Omega0, 'Rho': Rho, 'Ev_coef': Ev_coef,
                'drift_data': {'ratio': drift_ratio, 'note': drift_note, 'len_unit': len_unit}
            }
            return self.results
        except Exception as e:
            return {'error': str(e)}
        
    def export_spectrum_to_csv(self, filename):
        if not self.results or 'spectrum' not in self.results: return False, "No data."
        try:
            with open(filename, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['Periodo (s)', 'Aceleracion (g)'])
                for t, sa in zip(*self.results['spectrum']): w.writerow([f"{t:.4f}", f"{sa:.4f}"])
            return True, "Exportado correctamente."
        except Exception as e: return False, str(e)

    def generate_html_report(self, plot_img_base64=None):
        if not self.results or 'error' in self.results: return "<h3>Sin resultados.</h3>"
        r = self.results; inp = r['inputs']; u = inp.get('unit', 'kN')
        Ev = r.get('Ev_coef', 0); Rho = r.get('Rho', 1.0); Om = r.get('Omega0', 3.0)
        c5, c7 = 1.2 + Ev, 0.9 - Ev
        drift = r.get('drift_data', {'ratio': 0, 'note': '', 'len_unit': 'cm'})
        
        # --- ESTILOS CSS OPTIMIZADOS PARA PDF ---
        base_font_size = "10pt"
        header_font_size = "14pt"
        title_font_size = "18pt"
        
        table_style = 'border-collapse: collapse; width: 100%; border: 0.5pt solid #999; font-family: Arial, sans-serif; margin-bottom: 15pt;'
        th_style = f'background-color: #eee; border: 0.5pt solid #999; padding: 4pt; text-align: left; font-size: {base_font_size}; font-weight: bold;'
        td_style = f'border: 0.5pt solid #999; padding: 4pt; font-size: {base_font_size};'
        
        h1_style = f'color: #2c3e50; text-align:center; font-size: {title_font_size}; margin-bottom: 10pt;'
        h2_style = f'color: #2c3e50; border-bottom: 1pt solid #2c3e50; margin-top: 20pt; margin-bottom: 8pt; font-size: {header_font_size};'
        p_style = f'font-size: {base_font_size}; margin-bottom: 5pt;'
        
        # Estilo para caja de ecuaciones
        eq_style = f'font-family: "Times New Roman", Times, serif; font-size: 11pt; font-style: italic; background-color: #f9f9f9; padding: 8pt; border-left: 3pt solid #ccc; margin: 10pt 0;'
        
        # --- GENERACIÓN DEL HTML ---
        
        html = f"""
        <body style="font-family: Arial, sans-serif;">
        <h1 style="{h1_style}">Memoria de Cálculo Sísmico Detallada</h1>
        <p style="text-align:center; font-size: 9pt; color: #666; margin-bottom: 20pt;">Basado en ASCE 7-05 (Capítulos 11 y 12)</p>
        
        <h2 style="{h2_style}">1. Parámetros de Sitio y Diseño</h2>
        <table cellspacing="0" cellpadding="4" style="{table_style}">
          <thead>
              <tr><th style="{th_style}" width="40%">Parámetro</th><th style="{th_style}" width="30%">Valor</th><th style="{th_style}" width="30%">Referencia ASCE 7-05</th></tr>
          </thead>
          <tbody>
              <tr><td style="{td_style}">Ss / S1</td><td style="{td_style}">{inp['Ss']:.3f} g / {inp['S1']:.3f} g</td><td style="{td_style}">Mapas Caps. 22</td></tr>
              <tr><td style="{td_style}">Clase de Sitio</td><td style="{td_style}">{inp['SiteClass']}</td><td style="{td_style}">Tabla 20.3-1</td></tr>
              <tr><td style="{td_style}">Fa (Coef. Sitio)</td><td style="{td_style}">{r['Fa']:.2f}</td><td style="{td_style}">Tabla 11.4-1</td></tr>
              <tr><td style="{td_style}">Fv (Coef. Sitio)</td><td style="{td_style}">{r['Fv']:.2f}</td><td style="{td_style}">Tabla 11.4-2</td></tr>
              <tr><td style="{td_style}">Ie (Importancia)</td><td style="{td_style}">{inp['Ie']:.2f}</td><td style="{td_style}">Tabla 11.5-1</td></tr>
              <tr><td style="{td_style}">R (Mod. Respuesta)</td><td style="{td_style}">{inp['R']:.1f}</td><td style="{td_style}">Tabla 12.2-1</td></tr>
              <tr><td style="{td_style}">&Omega;<sub>0</sub> (Sobreresistencia)</td><td style="{td_style}">{Om:.1f}</td><td style="{td_style}">Tabla 12.2-1</td></tr>
          </tbody>
        </table>

        <h2 style="{h2_style}">2. Aceleraciones Espectrales de Diseño</h2>
        <p style="{p_style}">Se calculan según Sección 11.4.3 y 11.4.4:</p>
        <div style="{eq_style}">
            S<sub>MS</sub> = Fa &middot; Ss = {r['Fa']:.2f} &middot; {inp['Ss']:.2f} = <b>{r['SMS']:.3f} g</b> (Ec. 11.4-1)<br>
            S<sub>M1</sub> = Fv &middot; S1 = {r['Fv']:.2f} &middot; {inp['S1']:.2f} = <b>{r['SM1']:.3f} g</b> (Ec. 11.4-2)
        </div>
        <div style="{eq_style}">
            S<sub>DS</sub> = (2/3) &middot; S<sub>MS</sub> = <b>{r['SDS']:.3f} g</b> (Ec. 11.4-3)<br>
            S<sub>D1</sub> = (2/3) &middot; S<sub>M1</sub> = <b>{r['SD1']:.3f} g</b> (Ec. 11.4-4)
        </div>
        <p style="{p_style}"><b>Categoría de Diseño Sísmico (SDC):</b> {r['SDC']} (Tablas 11.6-1/2)</p>

        <h2 style="{h2_style}">3. Periodo Fundamental y Coeficiente Sísmico</h2>
        <div style="{eq_style}">
            T<sub>a</sub> = C<sub>t</sub> &middot; h<sub>n</sub><sup>x</sup> = {r['Ta']:.3f} s (Ec. 12.8-7)<br>
            T<sub>usado</sub> = min(C<sub>u</sub> T<sub>a</sub>, T<sub>model</sub>) = <b>{r['T_used']:.3f} s</b> (Sección 12.8.2)
        </div>
        <p style="{p_style}">Cálculo de C<sub>s</sub> (Sección 12.8.1.1):</p>
        <div style="{eq_style}">
             C<sub>s,calc</sub> = S<sub>DS</sub> / (R/Ie) = {r['Cs_calc']:.4f} (Ec. 12.8-2)<br>
             C<sub>s,max</sub> = S<sub>D1</sub> / (T(R/Ie)) = {r['Cs_max']:.4f} (Ec. 12.8-3/4)<br>
             C<sub>s,min</sub> = 0.044 S<sub>DS</sub> Ie = {r['Cs_min']:.4f} (Ec. 12.8-5)<br>
             <b>C<sub>s,diseño</sub> = {r['Cs']:.4f}</b>
        </div>
        
        <div style="background-color: #e8f6f3; padding: 10pt; border: 1pt solid #1abc9c; margin-top: 10pt;">
            <b style="color: #16a085; font-size: {base_font_size};">CORTANTE BASAL V = Cs &middot; W</b><br>
            <span style="font-size: {base_font_size};">V = {r['Cs']:.4f} &middot; {r['W_total']:.2f} {u} = <b>{r['V']:.2f} {u}</b> (Ec. 12.8-1)</span>
        </div>

        <h2 style="{h2_style}">4. Derivas de Piso Admisibles (Drift)</h2>
        <p style="{p_style}">Verificación requerida según Sección 12.12. El desplazamiento &delta;<sub>x</sub> (calculado elásticamente) debe multiplicarse por C<sub>d</sub>/Ie antes de comparar con &Delta;<sub>a</sub>.</p>
        <table cellspacing="0" cellpadding="4" style="{table_style}">
          <tr>
            <td style="{td_style}" width="40%"><b>Límite &Delta;<sub>a</sub> / h</b></td>
            <td style="{td_style}" width="30%">{drift['ratio']:.4f}</td>
            <td style="{td_style}" width="30%">{drift['note']}</td>
          </tr>
        </table>
        
        <table cellspacing="0" cellpadding="4" style="{table_style}">
          <thead>
            <tr style="background-color: #fcf3cf;">
                <th style="{th_style}">Nivel</th>
                <th style="{th_style}">Altura h<sub>i</sub> (m)</th>
                <th style="{th_style}">Deriva Máx. &Delta;<sub>a</sub> ({drift['len_unit']})</th>
            </tr>
          </thead>
          <tbody>
        """
        for d in r['distribution'][::-1]:
            html += f"<tr><td style='{td_style}'>{d['name']}</td><td style='{td_style}'>{d['h_story']:.2f}</td><td style='{td_style}'><b>{d['Da_disp']:.2f}</b></td></tr>"
        html += "</tbody></table>"
        
        # --- CÁLCULO DE K (NUEVO) ---
        T_val = r['T_used']
        k_val = r['k']
        if T_val <= 0.5:
            calc_k_html = f"Como T = {T_val:.3f} s &le; 0.5 s, se usa <b>k = 1.0</b>"
        elif T_val >= 2.5:
            calc_k_html = f"Como T = {T_val:.3f} s &ge; 2.5 s, se usa <b>k = 2.0</b>"
        else:
            calc_k_html = f"Como 0.5 < T < 2.5 s, se interpola linealmente:<br>k = 1 + (T - 0.5)/2 = 1 + ({T_val:.3f} - 0.5)/2 = <b>{k_val:.3f}</b>"

        html += f"""
        <h2 style="{h2_style}">5. Distribución Vertical de Fuerzas</h2>
        <p style="{p_style}">Cálculo del exponente <b>k</b> según Sección 12.8.3:</p>
        <div style="{eq_style}">
            {calc_k_html}
        </div>
        <p style="{p_style}">Distribución según Ec. 12.8-11 y 12.8-12:</p>
        <table cellspacing="0" cellpadding="4" style="{table_style}">
          <thead>
            <tr style="background-color: #f2f2f2;">
                <th style="{th_style}">Nivel x</th>
                <th style="{th_style}">h<sub>x</sub> (m)</th>
                <th style="{th_style}">w<sub>x</sub> ({u})</th>
                <th style="{th_style}">C<sub>vx</sub></th>
                <th style="{th_style}">F<sub>x</sub> ({u})</th>
                <th style="{th_style}">V<sub>x</sub> ({u})</th>
            </tr>
          </thead>
          <tbody>
        """
        
        for d in r['distribution'][::-1]:
            html += f"""<tr>
                <td style='{td_style}'>{d['name']}</td>
                <td style='{td_style}'>{d['hx']:.2f}</td>
                <td style='{td_style}'>{d['w']:.0f}</td>
                <td style='{td_style}'>{d['Cvx']:.4f}</td>
                <td style='{td_style}'><b>{d['Fx']:.2f}</b></td>
                <td style='{td_style}'>{d['Vx']:.2f}</td>
            </tr>"""
        html += "</tbody></table>"
        
        html += f"""
        <h2 style="{h2_style}">6. Combinaciones de Carga Sísmica</h2>
        <p style="{p_style}">Efecto de carga sísmica E = &rho;Q<sub>E</sub> &plusmn; 0.2S<sub>DS</sub>D (Sección 12.4.2)</p>
        <table cellspacing="0" cellpadding="4" style="{table_style}">
            <thead>
                <tr><th style="{th_style}" width="40%">Ecuación</th><th style="{th_style}" width="60%">Combinación Expandida</th></tr>
            </thead>
            <tbody>
                <tr><td style="{td_style}">(5) 1.2D + 1.0E + L</td><td style="{td_style}">({c5:.3f})D + {Rho:.1f}Q<sub>E</sub> + L</td></tr>
                <tr><td style="{td_style}">(7) 0.9D + 1.0E</td><td style="{td_style}">({c7:.3f})D + {Rho:.1f}Q<sub>E</sub></td></tr>
            </tbody>
        </table>
        """

        if plot_img_base64:
            # Usar width en porcentaje y max-width para asegurar que la imagen no rompa el layout
            html += f"""
            <div style="page-break-before: always;"></div>
            <h2 style="{h2_style}">7. Gráficos</h2>
            <div style="text-align: center; margin-top: 20pt;">
                <img src="data:image/png;base64,{plot_img_base64}" 
                     width="600" style="max-width: 100%; border: 1pt solid #ccc;" />
            </div>
            """
            
        html += "</body>"
        return html