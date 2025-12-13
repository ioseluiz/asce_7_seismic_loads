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
        
        self.btn_calc = QPushButton("CALCULAR CARGAS")
        self.btn_calc.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px; background-color: #007bff; color: white;")
        input_layout.addWidget(self.btn_calc)
        
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
                h = float(self.stories_table.item(i, 0).text())
                w = float(self.stories_table.item(i, 1).text())
                stories.append({'h': h, 'w': w, 'id': i+1})
            except ValueError:
                pass # Ignorar filas vacías o invalidas
                
        return {
            'unit': self.unit_combo.currentText(),
            'Ss': self.ss_input.value(),
            'S1': self.s1_input.value(),
            'TL': self.tl_input.value(),
            'SiteClass': self.site_class_combo.currentText(),
            'R': self.r_input.value(),
            'Ie': self.ie_input.value(),
            'StructureType': self.struct_type_combo.currentText(),
            'stories': stories
        }

    def plot_results(self, results):
        self.figure.clear()
        unit = results['inputs'].get('unit', 'kN')
        
        # Subplot 1: Espectro
        ax1 = self.figure.add_subplot(221)
        periods, sas = results['spectrum']
        ax1.plot(periods, sas, 'b-', linewidth=2)
        ax1.set_title("Espectro de Diseño (ASCE 7-05)")
        ax1.set_xlabel("Periodo T (s)")
        ax1.set_ylabel("Sa (g)")
        ax1.grid(True, linestyle='--', alpha=0.6)
        
        # Marcar T de la estructura
        T_struct = results['T_used']
        Sa_struct = results['Cs'] * (results['inputs']['R']/results['inputs']['Ie']) # Aproximado para visual
        ax1.plot(T_struct, Sa_struct, 'ro', label=f'T={T_struct:.2f}s')
        ax1.legend()
        
        # Subplot 2: Diagrama del Edificio (Input Data Visualization)
        ax2 = self.figure.add_subplot(222)
        dist = results['distribution']
        
        heights = [0] + [d['hx'] for d in dist]
        
        for d in dist:
            h = d['hx']
            # Dibujar losa
            ax2.plot([-2, 2], [h, h], 'k-', linewidth=2)
            # Dibujar columnas (esquemático)
            prev_h = next((x['hx'] for x in dist if x['hx'] < h), 0)
            ax2.plot([-2, -2], [prev_h, h], 'k-', linewidth=1)
            ax2.plot([2, 2], [prev_h, h], 'k-', linewidth=1)
            
            # Etiqueta Peso (Aquí deberías aplicar conversión si el modelo no lo hace, 
            # pero por ahora mostramos la unidad seleccionada)
            ax2.text(0, h + 0.1, f"W={d['w']:.0f}", ha='center', fontsize=8)
            
        ax2.set_xlim(-5, 5)
        ax2.set_ylim(0, max(heights) * 1.1)
        ax2.set_title("Modelo Esquemático")
        ax2.axis('off')
        
        # Subplot 3: Distribución Vertical (Fuerzas)
        ax3 = self.figure.add_subplot(212)
        forces = [d['Fx'] for d in dist]
        h_vals = [d['hx'] for d in dist]
        
        ax3.barh(h_vals, forces, height=1.0, align='center', color='orange', alpha=0.7)
        ax3.set_title("Distribución Vertical de Fuerzas Sísmicas (Fx)")
        ax3.set_xlabel(f"Fuerza Lateral ({unit})")
        ax3.set_ylabel("Altura (m)")
        ax3.grid(True, axis='x', linestyle='--')
        
        for i, v in enumerate(forces):
            ax3.text(v, h_vals[i], f" {v:.1f} {unit}", va='center', fontweight='bold')
        
        # Ajuste automático de layout para evitar superposiciones
        self.figure.tight_layout()
        self.canvas.draw()