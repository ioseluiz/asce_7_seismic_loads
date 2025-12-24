import io
import base64
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QFormLayout, QLabel, QDoubleSpinBox, QComboBox, 
                             QPushButton, QTableWidget, QTableWidgetItem, 
                             QTabWidget, QTextEdit, QHeaderView, QSplitter)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class SeismicView(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Calculadora Sísmica ASCE 7-05 / REP-2021")
        self.resize(1200, 800)
        
        # Widget Central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout Principal
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
        self.site_class_combo.addItems(['A', 'B', 'C', 'D', 'E'])
        self.site_class_combo.setCurrentText('D')
        
        self.r_input = QDoubleSpinBox()
        self.r_input.setValue(8.0)

        self.omega_input = QDoubleSpinBox()
        self.omega_input.setRange(1.0, 3.0); self.omega_input.setSingleStep(0.5); self.omega_input.setValue(3.0)
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
        
        # Selector de Unidades
        self.unit_combo = QComboBox()
        self.unit_combo.addItems(['kN', 'Ton', 'kg'])
        self.unit_combo.setCurrentText('kN')
        self.unit_combo.setEnabled(False)
        self.unit_combo.setToolTip("Cambia las unidades de los resultados (Reporte y Gráficos)")

        form_layout.addRow("Unidades de Resultados:", self.unit_combo)
        form_layout.addRow("Ss (0.2s):", self.ss_input)
        form_layout.addRow("S1 (1.0s):", self.s1_input)
        form_layout.addRow("TL (Periodo Largo):", self.tl_input)
        form_layout.addRow("Clase de Sitio:", self.site_class_combo)
        form_layout.addRow("R (Mod. Respuesta):", self.r_input)
        form_layout.addRow("Ω0 (Sobreresistencia):", self.omega_input)
        form_layout.addRow("ρ (Redundancia):", self.rho_combo)
        form_layout.addRow("Ie (Importancia):", self.ie_input)
        form_layout.addRow("Tipo Estructura:", self.struct_type_combo)
        
        input_layout.addLayout(form_layout)
        
        # Tabla de Pisos
        input_layout.addWidget(QLabel("<b>Definición de Niveles</b>"))
        self.stories_table = QTableWidget()
        self.stories_table.setColumnCount(2)
        self.stories_table.setHorizontalHeaderLabels(["Altura Piso (m)", "Peso (kN)"])
        self.stories_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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

        # Boton Calcular
        self.btn_calc = QPushButton("CALCULAR CARGAS")
        self.btn_calc.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px; background-color: #007bff; color: white;")
        input_layout.addWidget(self.btn_calc)

        # Botones de Exportación
        export_layout = QHBoxLayout()
        
        self.btn_export_csv = QPushButton("CSV (Espectro)")
        self.btn_export_csv.setToolTip("Guardar espectro en CSV compatible con ETABS")
        self.btn_export_csv.setEnabled(False)

        self.btn_export_pdf = QPushButton("PDF (Reporte)")
        self.btn_export_pdf.setToolTip("Guardar memoria de cálculo completa con gráficos")
        self.btn_export_pdf.setEnabled(False)

        style_export = """
            QPushButton { font-weight: bold; padding: 8px; border-radius: 4px; }
            QPushButton:disabled { background-color: #e0e0e0; color: #a0a0a0; border: 1px solid #cccccc; }
            QPushButton:enabled { background-color: #28a745; color: white; border: 1px solid #218838; }
            QPushButton:enabled:hover { background-color: #218838; }
        """
        self.btn_export_csv.setStyleSheet(style_export)
        self.btn_export_pdf.setStyleSheet(style_export)

        export_layout.addWidget(self.btn_export_csv)
        export_layout.addWidget(self.btn_export_pdf)
        input_layout.addLayout(export_layout)
        
        splitter.addWidget(input_widget)
        
        # --- Panel Derecho (Resultados) ---
        self.tabs = QTabWidget()
        
        # Tab 1: Resumen y Reporte
        self.report_viewer = QTextEdit()
        self.report_viewer.setReadOnly(True)
        self.tabs.addTab(self.report_viewer, "Reporte")
        
        # Tab 2: Gráficos
        graphs_widget = QWidget()
        graphs_layout = QVBoxLayout(graphs_widget)
        
        self.figure = Figure(figsize=(5, 8)) # Tamaño inicial para GUI
        self.canvas = FigureCanvas(self.figure)
        graphs_layout.addWidget(self.canvas)
        
        self.tabs.addTab(graphs_widget, "Gráficos y Diagramas")
        
        splitter.addWidget(self.tabs)
        splitter.setSizes([400, 800])

        # Footer
        footer_label = QLabel("© 2025 Ing. Jose Luis Muñoz | Todos los derechos reservados")
        footer_label.setAlignment(Qt.AlignCenter)
        footer_label.setStyleSheet("font-size: 11px; color: #555; padding: 10px; background-color: #f0f0f0; border-top: 1px solid #ccc;")
        main_layout.addWidget(footer_label)

    def get_inputs(self):
        stories = []
        rows = self.stories_table.rowCount()
        for i in range(rows):
            try:
                item_h = self.stories_table.item(i, 0)
                item_w = self.stories_table.item(i, 1)
                if item_h and item_w and item_h.text() and item_w.text():
                    h = float(item_h.text())
                    w = float(item_w.text())
                    stories.append({'h': h, 'w': w, 'id': i+1})
            except ValueError:
                pass 
                
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
        periods, sas = results['spectrum']
        T0, Ts, TL = results['T0'], results['Ts'], results['inputs']['TL']
        SDS, SD1 = results['SDS'], results['SD1']
        
        # 1. ESPECTRO (Gráfico Superior)
        ax1 = self.figure.add_subplot(211) 
        ax1.plot(periods, sas, 'k-', linewidth=2.5, label='Espectro ASCE 7-05')
        max_sa = max(sas)
        y_top = max_sa * 1.25 
        ax1.set_ylim(0, y_top)
        ax1.set_xlim(0, max(periods))
        ax1.vlines([T0, Ts, TL], 0, y_top, colors='gray', linestyles=':', linewidth=1)
        
        ax1.axvspan(0, T0, alpha=0.1, color='red')
        ax1.text(T0/2, SDS*0.5, r'$T < T_0$', ha='center', fontsize=9, color='darkred', rotation=90)
        ax1.axvspan(T0, Ts, alpha=0.1, color='yellow')
        ax1.text((T0+Ts)/2, SDS + (y_top*0.02), r'$S_{DS}$', ha='center', va='bottom', fontsize=9, fontweight='bold')
        ax1.axvspan(Ts, TL, alpha=0.1, color='green')
        
        T_struct = results['T_used']
        Sa_struct = results['Cs'] * (results['inputs']['R']/results['inputs']['Ie'])
        ax1.plot(T_struct, Sa_struct, 'ro', markersize=8, zorder=5, label=f'T={T_struct:.3f}s')
        
        ax1.set_title("Espectro de Diseño", fontsize=11, fontweight='bold')
        ax1.set_ylabel("Sa (g)")
        ax1.set_xlabel("Periodo (s)")
        ax1.grid(True, linestyle=':', alpha=0.6)
        ax1.legend(loc='upper right', frameon=True, fontsize='small')

        # 2. MODELO ESTRUCTURAL CON CARGAS (Gráfico Inferior Izquierdo)
        ax2 = self.figure.add_subplot(223)
        dist = results['distribution']
        heights = [0] + [d['hx'] for d in dist]
        
        # Dibujar la estructura y las flechas
        for d in dist:
            h = d['hx']
            fx = d['Fx']
            
            # Dibujo del pórtico
            ax2.plot([-2, 2], [h, h], 'k-', linewidth=2) # Vigas
            
            # Columnas hacia abajo
            prev_h = next((x['hx'] for x in dist if x['hx'] < h), 0)
            ax2.plot([-2, -2], [prev_h, h], 'k-', linewidth=1) # Columna Izq
            ax2.plot([2, 2], [prev_h, h], 'k-', linewidth=1)   # Columna Der
            
            # Etiqueta de peso (W) en el centro
            ax2.text(0, h + 0.2, f"W={d['w']:.0f}", ha='center', fontsize=7, color='#555')
            
            # --- NUEVO: Flecha de Fuerza Horizontal ---
            # Dibuja una flecha roja apuntando desde la izquierda hacia el nodo izquierdo
            ax2.annotate(
                f"F={fx:.1f}", 
                xy=(-2, h),           # Punta de la flecha (en el nodo)
                xytext=(-4.5, h),     # Cola de la flecha (más a la izquierda)
                arrowprops=dict(facecolor='#d35400', edgecolor='none', shrink=0.05, width=2, headwidth=8),
                fontsize=8,
                color='#d35400',
                fontweight='bold',
                va='center',
                ha='right'
            )

        ax2.set_xlim(-6, 3) # Ampliamos el límite izquierdo para que quepan las flechas
        ax2.set_ylim(0, max(heights) * 1.15)
        ax2.set_title(f"Modelo y Cargas ({unit})", fontsize=10)
        ax2.axis('off') # Ocultar ejes para que parezca un diagrama puro

        # 3. DIAGRAMA DE BARRAS DE FUERZAS (Gráfico Inferior Derecho)
        ax3 = self.figure.add_subplot(224)
        forces = [d['Fx'] for d in dist]
        h_vals = [d['hx'] for d in dist]
        
        # Barras horizontales
        ax3.barh(h_vals, forces, height=max(h_vals)*0.05, align='center', color='orange', alpha=0.7, edgecolor='black')
        
        ax3.set_title(f"Perfil de Fuerzas Fx ({unit})", fontsize=10)
        ax3.grid(True, axis='x', linestyle='--', alpha=0.5)
        x_limit = max(forces) * 1.3 if forces else 1
        ax3.set_xlim(0, x_limit)
        
        # Etiquetas de valor al final de las barras
        for i, v in enumerate(forces):
            ax3.text(v, h_vals[i], f" {v:.1f}", va='center', fontsize=8, fontweight='bold')

        self.figure.tight_layout()
        self.figure.subplots_adjust(hspace=0.4, bottom=0.1) 
        self.canvas.draw()

    def get_plot_image_base64(self):
        """
        Captura la figura actual de Matplotlib, la redimensiona para reporte PDF
        (7.5x9.0 pulgadas para respetar margenes de hoja carta), y retorna base64.
        """
        # 1. Guardar tamaño original (pequeño, para la GUI)
        original_size = self.figure.get_size_inches()

        # 2. Tamaño para PDF (Ligeramente menor que 8.5x11 para margenes)
        self.figure.set_size_inches(6.0, 7.5) 
        
        buf = io.BytesIO()
        self.figure.savefig(buf, format='png', bbox_inches='tight', dpi=150)
        buf.seek(0)
        img_data = base64.b64encode(buf.read()).decode('utf-8')

        # 3. Restaurar tamaño original
        self.figure.set_size_inches(original_size)
        self.canvas.draw()

        return img_data