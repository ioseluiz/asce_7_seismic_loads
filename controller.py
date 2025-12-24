from PyQt5.QtWidgets import QMessageBox, QFileDialog

class SeismicController:
    """
    Controlador que conecta la Vista y el Modelo.
    Maneja eventos de usuario y actualiza la GUI.
    """
    def __init__(self, model, view):
        self.model = model
        self.view = view
        
        # Conectar señales de botones
        self.view.btn_calc.clicked.connect(self.handle_calculate)
        self.view.btn_add_row.clicked.connect(self.add_story)
        self.view.btn_del_row.clicked.connect(self.del_story)

        self.view.btn_export.clicked.connect(self.handle_export_csv)
        
        # Conectar señal de cambio de unidad (Recalcular al cambiar)
        self.view.unit_combo.currentIndexChanged.connect(self.handle_calculate)
        
    def add_story(self):
        row = self.view.stories_table.rowCount()
        self.view.stories_table.insertRow(row)
        
    def del_story(self):
        row = self.view.stories_table.rowCount()
        if row > 0:
            self.view.stories_table.removeRow(row - 1)
            
    def handle_calculate(self):
        inputs = self.view.get_inputs()
        
        # Validaciones básicas
        if not inputs['stories']:
            QMessageBox.warning(self.view, "Error", "Debe definir al menos un nivel/piso.")
            return
            
        # Calcular
        results = self.model.calculate_loads(inputs)
        
        if 'error' in results:
            QMessageBox.critical(self.view, "Error de Cálculo", str(results['error']))
            return
        
        # Habilitar el selector de unidades ahora que hay resultados
        self.view.unit_combo.setEnabled(True)
        self.view.btn_export.setEnabled(True)
            
        # Generar Reporte (Cambiamos setMarkdown por setHtml)
        report_html = self.model.generate_html_report()
        self.view.report_viewer.setHtml(report_html)
        
        # Generar Gráficos
        self.view.plot_results(results)
        
        # Cambiar a tab de resultados si es la primera vez (opcional)
        # self.view.tabs.setCurrentIndex(0)

    def handle_export_csv(self):
        """
        Maneja la exportacion del archivo CSV mediante dialogo.
        """

        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(
            self.view,
            "Guardar espectro de diseño",
            "espectro_asce7_05.csv",
            "Archivos CSV (*.csv);;Todos los archivos (*)",
            options=options
        )

        if fileName:
            success, message = self.model.export_spectrum_to_csv(fileName)
            if success:
                QMessageBox.information(self.view, "Exportación Exitosa", message)
            else:
                QMessageBox.critical(self.view, "Error de Exportación", message)