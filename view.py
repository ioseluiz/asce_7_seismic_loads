from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QFormLayout, QLabel, QDoubleSpinBox, QComboBox, 
                             QPushButton, QTableWidget, QTableWidgetItem, 
                             QTabWidget, QTextEdit, QHeaderView, QSplitter)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

class SeismicView(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Calculadora Sísmica ASCE 7-05")
        self.resize(1200, 800)
        
        # Widget Central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Cambiamos a QVBoxLayout para apilar el contenido y el footer
        main_layout = QVBoxLayout(central_widget)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # --- Panel Izquierdo (Entradas) ---
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        
        # Formulario de parámetros sísmicos
        form_layout = QFormLayout()
        
        self.ss_input = QDoubleSpinBox()
        self.ss_input.setRange(0, 5.0); self.ss_input.setSingleStep(0.05); self.ss_input.setValue(1.5)
        
        self.s1_input = QDoubleSpinBox()
        self.s1_input.setRange(0, 3.0); self.s1_input.setSingleStep(0.05); self.s1_input.setValue(0.6)
        
        self.tl_input = QDoubleSpinBox()
        self.tl_input.setRange(0, 20.0); self.tl_input.setValue(8.0)
        
        self.site_class_combo = QComboBox()
        self.site_class_combo.addItems(['A', 'B', 'C', 'D', 'E']) # F omitido por simplicidad
        self.site_class_combo.setCurrentText('D')
        
        self.r_input = QDoubleSpinBox()
        self.r_input.setValue(8.0)

        self.omega_input = QDoubleSpinBox()
        self.omega_input.setRange(1.0, 3.0)
        self.omega_input.setSingleStep(0.5)
        self.omega_input.setValue(3.0)
        self.omega_input.setToolTip("Factor de Sobreresistencia del sistema (Tabla 12.2-1)")

        self.rho_combo = QComboBox()
        self.rho_combo.addItems(['1.0', '1.3'])
        self.rho_combo.setToolTip("Factor de Redundancia (Sección 12.3.4)")
        
        self.ie_input = QDoubleSpinBox()
        self.ie_input.setValue(1.0)
        
        self.struct_type_combo = QComboBox()
        self.struct_type_combo.addItems([
            'Acero (Pórticos Resistentes a Momento)',
            'Concreto (Pórticos Resistentes a Momento)',
            'Pórticos con Arriostramiento Excéntrico',
            'Otros Sistemas'
        ])
        
        # Selector de Unidades (Solo para resultados)
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(['kN', 'Ton', 'kg'])
        self.unit_combo.setCurrentText('kN')
        self.unit_combo.setEnabled(False) # Deshabilitado hasta calcular
        self.unit_combo.setToolTip("Cambia las unidades de los resultados (Reporte y Gráficos)")

        form_layout.addRow("Unidades de Resultados:", self.unit_combo)
        form_layout.addRow("Ss (0.2s):", self.ss_input)
        form_layout.addRow("S1 (1.0s):", self.s1_input)
        form_layout.addRow("TL (Periodo Largo):", self.tl_input)
        form_layout.addRow("Clase de Sitio:", self.site_class_combo)
        form_layout.addRow("R (Mod. Respuesta):", self.r_input)
        form_layout.addRow("Ω0 (Sobreresistencia):", self.omega_input)  # <--- NUEVO
        form_layout.addRow("ρ (Redundancia):", self.rho_combo)
        form_layout.addRow("Ie (Importancia):", self.ie_input)
        form_layout.addRow("Tipo Estructura:", self.struct_type_combo)
        
        input_layout.addLayout(form_layout)
        
        # Tabla de Pisos
        input_layout.addWidget(QLabel("<b>Definición de Niveles</b>"))
        self.stories_table = QTableWidget()
        self.stories_table.setColumnCount(2)
        # Headers iniciales fijos (Entrada siempre en kN por defecto para consistencia)
        self.stories_table.setHorizontalHeaderLabels(["Altura Piso (m)", "Peso (kN)"])
        self.stories_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # Valores por defecto
        self.stories_table.setRowCount(3)
        for i in range(3):
            self.stories_table.setItem(i, 0, QTableWidgetItem("3.5"))
            self.stories_table.setItem(i, 1, QTableWidgetItem("2000"))
            
        input_layout.addWidget(self.stories_table)
        
        # Botones tabla
        btn_layout = QHBoxLayout()
        self.btn_add_row = QPushButton("+ Nivel")
        self.btn_del_row = QPushButton("- Nivel")
        btn_layout.addWidget(self.btn_add_row)
        btn_layout.addWidget(self.btn_del_row)
        input_layout.addLayout(btn_layout)

        # Botones de Accion
        self.btn_calc = QPushButton("CALCULAR CARGAS")
        self.btn_calc.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px; background-color: #007bff; color: white;")
        input_layout.addWidget(self.btn_calc)

        # Boton para Exportar CSV
        self.btn_export = QPushButton("Exportar Espectro (.csv)")

        # DEFINICIÓN DE ESTILOS DINÁMICOS (CSS)
        self.btn_export.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            
            /* Estado DESHABILITADO: Gris opaco */
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #a0a0a0;
                border: 1px solid #cccccc;
            }

            /* Estado HABILITADO: Verde éxito (Tu color de UI) */
            QPushButton:enabled {
                background-color: #28a745;
                color: white;
                border: 1px solid #218838;
            }
            
            /* Opcional: Efecto al pasar el mouse cuando está habilitado */
            QPushButton:enabled:hover {
                background-color: #218838;
            }
        """)


        self.btn_export.setStyleSheet("font-weight: bold; padding: 8px; background-color: #28a745; color: white;")
        self.btn_export.setEnabled(False) # Deshabilitado hasta calcular
        self.btn_export.setToolTip("Genera un archivo CSV compatible con ETABS/SAP2000")
        input_layout.addWidget(self.btn_export)
        
        splitter.addWidget(input_widget)
        
        # --- Panel Derecho (Resultados) ---
        self.tabs = QTabWidget()
        
        # Tab 1: Resumen y Reporte
        self.report_viewer = QTextEdit()
        self.report_viewer.setReadOnly(True)
        self.tabs.addTab(self.report_viewer, "Reporte Markdown")
        
        # Tab 2: Gráficos
        graphs_widget = QWidget()
        graphs_layout = QVBoxLayout(graphs_widget)
        
        self.figure = Figure(figsize=(5, 8))
        self.canvas = FigureCanvas(self.figure)
        graphs_layout.addWidget(self.canvas)
        
        self.tabs.addTab(graphs_widget, "Gráficos y Diagramas")
        
        splitter.addWidget(self.tabs)
        splitter.setSizes([400, 800])

        # --- Footer (Copyright) ---
        footer_label = QLabel("© 2025 Ing. Jose Luis Muñoz\nTodos los derechos reservados")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setStyleSheet("""
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
                font-weight: bold;
                color: #555555;
                padding: 10px;
                background-color: #f0f0f0;
                border-top: 1px solid #cccccc;
            }
        """)
        main_layout.addWidget(footer_label)

    def get_inputs(self):
        """Recopila datos de la GUI"""
        stories = []
        rows = self.stories_table.rowCount()
        for i in range(rows):
            try:
                item_h = self.stories_table.item(i, 0)
                item_w = self.stories_table.item(i, 1)
                
                # Validación extra para evitar crashes si la celda está vacía
                if item_h and item_w and item_h.text() and item_w.text():
                    h = float(item_h.text())
                    w = float(item_w.text())
                    stories.append({'h': h, 'w': w, 'id': i+1})
            except ValueError:
                pass 
                
        # AQUÍ ESTABA EL ERROR POTENCIAL DE INDENTACIÓN
        return {
            'unit': self.unit_combo.currentText(),
            'Ss': self.ss_input.value(),
            'S1': self.s1_input.value(),
            'TL': self.tl_input.value(),
            'SiteClass': self.site_class_combo.currentText(),
            'R': self.r_input.value(),
            'Omega0': self.omega_input.value(),
            'Rho': float(self.rho_combo.currentText()),
            'Ie': self.ie_input.value(),
            'StructureType': self.struct_type_combo.currentText(),
            'stories': stories
        }

    def plot_results(self, results):
        self.figure.clear()
        unit = results['inputs'].get('unit', 'kN')
        
        # Datos necesarios
        periods, sas = results['spectrum']
        T0 = results['T0']
        Ts = results['Ts']
        TL = results['inputs']['TL']
        SDS = results['SDS']
        SD1 = results['SD1']
        
        # ==========================================================
        # 1. GRÁFICO DE ESPECTRO (Arreglado)
        # ==========================================================
        ax1 = self.figure.add_subplot(211) 
        
        # Curva principal
        ax1.plot(periods, sas, 'k-', linewidth=2.5, label='Espectro ASCE 7-05')
        
        # Definimos un límite Y con un 20% de "aire" arriba para que quepan los textos
        max_sa = max(sas)
        y_top = max_sa * 1.25 
        ax1.set_ylim(0, y_top)
        ax1.set_xlim(0, max(periods))

        # Líneas verticales de referencia
        ax1.vlines([T0, Ts, TL], 0, y_top, colors='gray', linestyles=':', linewidth=1)
        
        # --- Zonas y Etiquetas Mejoradas ---
        
        # Zona 1: T < T0 (Rojo)
        # Rotamos el texto 90 grados para que quepa en la franja estrecha
        ax1.axvspan(0, T0, alpha=0.1, color='red')
        ax1.text(T0/2, SDS*0.5, r'$T < T_0$', ha='center', va='center', 
                 fontsize=9, color='darkred', rotation=90)
        
        # Zona 2: Meseta (Amarillo)
        ax1.axvspan(T0, Ts, alpha=0.1, color='yellow')
        # Colocamos el texto justo ENCIMA de la meseta, centrado
        ax1.text((T0+Ts)/2, SDS + (y_top*0.02), r'$S_{DS}$ (Meseta)', 
                 ha='center', va='bottom', fontsize=9, fontweight='bold')
        
        # Zona 3: Periodo Largo (Verde)
        ax1.axvspan(Ts, TL, alpha=0.1, color='green')
        # Fórmula desplazada para no tocar la línea
        mid_T_long = (Ts + TL) / 2
        sa_mid = SD1 / mid_T_long
        ax1.text(mid_T_long, sa_mid + (y_top*0.05), r'$S_a = \frac{S_{D1}}{T}$', 
                 ha='center', va='bottom', fontsize=10)
        
        # Zona 4: T > TL (Azul)
        max_T_graph = max(periods)
        if max_T_graph > TL:
            ax1.axvspan(TL, max_T_graph, alpha=0.1, color='blue')
            # Texto ajustado a la derecha si hay espacio
            sa_long = (SD1 * TL) / ((TL+1)**2)
            ax1.text(TL + 0.5, sa_long + (y_top*0.05), r'$S_a = \frac{S_{D1} \cdot T_L}{T^2}$', 
                     ha='left', va='bottom', fontsize=10)

        # --- ETIQUETAS EJE X (Debajo del eje para no chocar) ---
        # Usamos transformación para ubicar el texto relativo al eje, no a los datos
        trans = ax1.get_xaxis_transform()
        
        # Offset vertical negativo (-0.12) para ponerlo debajo de los números
        ax1.text(T0, -0.12, f'To\n{T0:.2f}s', transform=trans, ha='center', va='top', fontsize=8, color='dimgray')
        ax1.text(Ts, -0.12, f'Ts\n{Ts:.2f}s', transform=trans, ha='center', va='top', fontsize=8, color='dimgray')
        ax1.text(TL, -0.12, f'TL\n{TL:.0f}s', transform=trans, ha='center', va='top', fontsize=8, color='dimgray')

        # Punto de la Estructura
        T_struct = results['T_used']
        Sa_struct = results['Cs'] * (results['inputs']['R']/results['inputs']['Ie'])
        ax1.plot(T_struct, Sa_struct, 'ro', markersize=8, zorder=5, label=f'Estructura T={T_struct:.3f}s')
        
        # Configuración final 
        ax1.set_title("Espectro de Respuesta de Diseño", fontsize=11, fontweight='bold', pad=20)
        ax1.set_ylabel("Sa (g)")
        ax1.set_xlabel("Periodo T (s)")
        ax1.grid(True, linestyle=':', alpha=0.6)
        ax1.legend(loc='upper right', frameon=True, fontsize='small')

        # ==========================================================
        # 2. MODELO ESQUEMÁTICO (Sin cambios mayores)
        # ==========================================================
        ax2 = self.figure.add_subplot(223)
        dist = results['distribution']
        heights = [0] + [d['hx'] for d in dist]
        
        for d in dist:
            h = d['hx']
            ax2.plot([-2, 2], [h, h], 'k-', linewidth=2)
            prev_h = next((x['hx'] for x in dist if x['hx'] < h), 0)
            ax2.plot([-2, -2], [prev_h, h], 'k-', linewidth=1)
            ax2.plot([2, 2], [prev_h, h], 'k-', linewidth=1)
            ax2.text(0, h + 0.1, f"W={d['w']:.0f}", ha='center', fontsize=8)
            
        ax2.set_xlim(-5, 5)
        ax2.set_ylim(0, max(heights) * 1.15)
        ax2.set_title("Modelo")
        ax2.axis('off')

        # ==========================================================
        # 3. FUERZAS (Sin cambios mayores)
        # ==========================================================
        ax3 = self.figure.add_subplot(224)
        forces = [d['Fx'] for d in dist]
        h_vals = [d['hx'] for d in dist]
        
        ax3.barh(h_vals, forces, height=max(h_vals)*0.05, align='center', color='orange', alpha=0.7, edgecolor='black')
        ax3.set_title(f"Fuerzas Fx ({unit})")
        ax3.set_xlabel("Fuerza")
        ax3.grid(True, axis='x', linestyle='--', alpha=0.5)
        
        x_limit = max(forces) * 1.3 if forces else 1
        ax3.set_xlim(0, x_limit)
        
        for i, v in enumerate(forces):
            ax3.text(v, h_vals[i], f" {v:.1f}", va='center', fontsize=8, fontweight='bold')

        self.figure.tight_layout()
        # Ajuste extra para que no se corten los textos de abajo
        self.figure.subplots_adjust(hspace=0.4, bottom=0.1) 
        self.canvas.draw()