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
        return np.interp(value, distinct_values, coeffs)

    def get_fa(self, site_class, ss):
        ss_vals = [0.25, 0.50, 0.75, 1.00, 1.25]
        table = {
            'A': [0.8, 0.8, 0.8, 0.8, 0.8], 'B': [1.0, 1.0, 1.0, 1.0, 1.0],
            'C': [1.2, 1.2, 1.1, 1.0, 1.0], 'D': [1.6, 1.4, 1.2, 1.1, 1.0],
            'E': [2.5, 1.7, 1.2, 0.9, 0.9], 'F': [None] * 5 
        }
        if site_class == 'F': return None
        return self.interpolate_coeff(ss, ss_vals, table[site_class])

    def get_fv(self, site_class, s1):
        s1_vals = [0.10, 0.20, 0.30, 0.40, 0.50]
        table = {
            'A': [0.8, 0.8, 0.8, 0.8, 0.8], 'B': [1.0, 1.0, 1.0, 1.0, 1.0],
            'C': [1.7, 1.6, 1.5, 1.4, 1.3], 'D': [2.4, 2.0, 1.8, 1.6, 1.5],
            'E': [3.5, 3.2, 2.8, 2.4, 2.4], 'F': [None] * 5
        }
        if site_class == 'F': return None
        return self.interpolate_coeff(s1, s1_vals, table[site_class])

    def get_sdc(self, sds, sd1, ie):
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
            
            Cu_val = np.interp(SD1, [0.1, 0.15, 0.2, 0.3, 0.4], [1.7, 1.6, 1.5, 1.4, 1.4])
            if SD1 > 0.4: Cu_val = 1.4
            T_upper = Cu_val * Ta
            T_used = min(T_upper, Ta)
            
            R = inputs['R']; Ie = inputs['Ie']; TL = inputs['TL']
            if R == 0: R = 1.0
            
            Cs_calc = SDS / (R / Ie)
            if T_used <= TL: Cs_max = SD1 / (T_used * (R / Ie))
            else: Cs_max = (SD1 * TL) / (T_used**2 * (R / Ie))
                
            Cs_min = 0.01 
            Cs_min_2 = 0.044 * SDS * Ie
            if Cs_min_2 < 0.01: Cs_min_2 = 0.01
            Cs_min_3 = (0.5 * S1) / (R / Ie) if S1 >= 0.6 else 0.0
            Cs = max(min(Cs_calc, Cs_max), Cs_min_2, Cs_min_3, Cs_min)

            Ev_coef = 0.2 * SDS
            W_total_kN = sum([p['w'] for p in stories])
            V_kN = Cs * W_total_kN
            
            if T_used <= 0.5: k = 1.0
            elif T_used >= 2.5: k = 2.0
            else: k = 1 + ((T_used - 0.5) / 2.0)
            
            temp_h = 0; story_data = []
            for story in stories:
                temp_h += story['h']
                story_data.append({'w_kN': story['w'], 'hx': temp_h, 'name': story.get('name', f"Nivel {temp_h:.1f}")})
                
            sum_whk = sum([item['w_kN'] * (item['hx'] ** k) for item in story_data])
            
            unit = inputs.get('unit', 'kN')
            f_conv = {'kN': 1.0, 'Ton': 0.10197, 'kg': 101.97}.get(unit, 1.0)
            
            W_total_out = W_total_kN * f_conv; V_out = V_kN * f_conv
            fx_list_out = []
            
            if sum_whk > 0:
                for item in story_data:
                    cvx = (item['w_kN'] * (item['hx'] ** k)) / sum_whk
                    fx_kN = cvx * V_kN
                    item.update({'w': item['w_kN']*f_conv, 'Fx': fx_kN*f_conv, 'Cvx': cvx})
                    fx_list_out.append(item['Fx'])
                
                accum = 0; shears = []
                for f in reversed(fx_list_out): accum += f; shears.insert(0, accum)
                for i, item in enumerate(story_data): item['Vx'] = shears[i]
            
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
                'Ta': Ta, 'T_used': T_used, 'Cu': Cu_val, 'Cs': Cs, 
                'W_total': W_total_out, 'V': V_out, 'k': k,
                'T0': T0, 'Ts': Ts,
                'distribution': story_data, 'spectrum': (p_range, sa_vals),
                'inputs': inputs, 'SDC': SDC, 'Omega0': Omega0, 'Rho': Rho, 'Ev_coef': Ev_coef
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
        
        table_style = 'border-collapse: collapse; width: 100%; border: 1px solid #ddd; page-break-inside: avoid;'
        th_style = 'background-color: #f2f2f2; border: 1px solid #ddd; padding: 6px; text-align: left;'
        td_style = 'border: 1px solid #ddd; padding: 6px;'
        
        html = f"""
        <h1 style="color: #2c3e50;">Memoria de Cálculo Sísmico (ASCE 7-05)</h1>
        <hr>
        <h2 style="color: #34495e;">1. Parámetros de Diseño</h2>
        <table style="{table_style}">
          <tr><th style="{th_style}">Parámetro</th><th style="{th_style}">Valor</th></tr>
          <tr><td style="{td_style}">Ss / S1</td><td style="{td_style}">{inp['Ss']:.3f} g / {inp['S1']:.3f} g</td></tr>
          <tr><td style="{td_style}">Sitio / TL</td><td style="{td_style}">{inp['SiteClass']} / {inp['TL']:.1f} s</td></tr>
          <tr><td style="{td_style}">Ie / R</td><td style="{td_style}">{inp['Ie']:.2f} / {inp['R']:.1f}</td></tr>
        </table>

        <h2 style="color: #34495e;">2. Coeficientes Sísmicos</h2>
        <table style="{table_style}">
            <tr><th style="{th_style}">Var</th><th style="{th_style}">Valor</th><th style="{th_style}">Var</th><th style="{th_style}">Valor</th></tr>
            <tr><td style="{td_style}">Fa</td><td style="{td_style}">{r['Fa']:.3f}</td><td style="{td_style}">Fv</td><td style="{td_style}">{r['Fv']:.3f}</td></tr>
            <tr><td style="{td_style}">SMS</td><td style="{td_style}">{r['SMS']:.3f} g</td><td style="{td_style}">SM1</td><td style="{td_style}">{r['SM1']:.3f} g</td></tr>
            <tr><td style="{td_style}">SDS</td><td style="{td_style}"><b>{r['SDS']:.3f} g</b></td><td style="{td_style}">SD1</td><td style="{td_style}"><b>{r['SD1']:.3f} g</b></td></tr>
        </table>
        
        <p><b>Periodo T</b> = {r['T_used']:.4f} s &nbsp;|&nbsp; <b>Coef. Cs</b> = {r['Cs']:.5f}</p>
        <p style="font-size:14px;"><b>Cortante Basal V = {r['V']:.2f} {u}</b></p>

        <h2 style="color: #34495e;">3. Combinaciones de Carga</h2>
        <table style="{table_style}">
          <tr><td style="{td_style}">Categoría (SDC)</td><td style="{td_style}"><b>{r['SDC']}</b></td></tr>
          <tr><td style="{td_style}">Factores (&rho; / &Omega;0)</td><td style="{td_style}">{Rho:.1f} / {Om:.1f}</td></tr>
        </table>
        <br>
        <table style="{table_style}">
            <tr style="background-color: #eaf2f8;"><th style="{td_style}">Comb. Básica</th><th style="{td_style}">Expandida (D + QE + L)</th></tr>
            <tr><td style="{td_style}">1.2D + 1.0E + L</td><td style="{td_style}"><b>({c5:.3f})D</b> + <b>{Rho:.1f}QE</b> + L</td></tr>
            <tr><td style="{td_style}">0.9D + 1.0E</td><td style="{td_style}"><b>({c7:.3f})D</b> + <b>{Rho:.1f}QE</b></td></tr>
        </table>

        <h2 style="color: #34495e;">4. Distribución Vertical</h2>
        <table style="{table_style}">
          <tr style="background-color: #f2f2f2;"><th>Nivel</th><th>h (m)</th><th>w ({u})</th><th>Fx ({u})</th><th>Vx ({u})</th></tr>
        """
        for d in r['distribution'][::-1]:
            html += f"<tr><td style='{td_style}'>{d['name']}</td><td style='{td_style}'>{d['hx']:.2f}</td><td style='{td_style}'>{d['w']:.2f}</td><td style='{td_style}'><b>{d['Fx']:.2f}</b></td><td style='{td_style}'>{d['Vx']:.2f}</td></tr>"
        html += "</table>"

        # INCRUSTAR IMAGEN DEL GRÁFICO (Con salto de página forzado)
        if plot_img_base64:
            html += f"""
            <div style="page-break-before: always;"></div>
            
            <h2 style="color: #34495e; margin-top: 20px;">5. Espectro y Diagramas</h2>
            <div style="text-align: center; width: 100%;">
                <img src="data:image/png;base64,{plot_img_base64}" 
                     style="width: 100%; max-height: 100%; object-fit: contain; border: 1px solid #ddd;" />
            </div>
            """

        return html