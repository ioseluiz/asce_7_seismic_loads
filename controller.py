from PyQt5.QtWidgets import QMessageBox, QFileDialog
from PyQt5.QtPrintSupport import QPrinter

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

        # Conectar exportaciones
        self.view.btn_export_csv.clicked.connect(self.handle_export_csv)
        self.view.btn_export_pdf.clicked.connect(self.handle_export_pdf)
        
        # Recalcular al cambiar unidad
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
        
        if not inputs['stories']:
            QMessageBox.warning(self.view, "Error", "Debe definir al menos un nivel/piso.")
            return
            
        results = self.model.calculate_loads(inputs)
        
        if 'error' in results:
            QMessageBox.critical(self.view, "Error de Cálculo", str(results['error']))
            return
        
        # Habilitar controles
        self.view.unit_combo.setEnabled(True)
        self.view.btn_export_csv.setEnabled(True)
        self.view.btn_export_pdf.setEnabled(True)
            
        # Generar Reporte (Texto simple en GUI)
        report_html = self.model.generate_html_report()
        self.view.report_viewer.setHtml(report_html)
        
        # Generar Gráficos
        self.view.plot_results(results)

    def handle_export_csv(self):
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

    def handle_export_pdf(self):
        """
        Exporta el reporte PDF incluyendo el gráfico actual.
        """
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(
            self.view,
            "Guardar reporte PDF",
            "Memoria_Calculo_Sismico.pdf",
            "Archivos PDF (*.pdf);;Todos los archivos (*)",
            options=options
        )

        if fileName:
            if not fileName.endswith('.pdf'):
                fileName += '.pdf'
                
            try:
                # 1. Capturar la imagen del gráfico
                img_data = self.view.get_plot_image_base64()
                
                # 2. Generar el HTML completo INCLUYENDO la imagen
                full_html = self.model.generate_html_report(plot_img_base64=img_data)
                
                # 3. Guardar estado actual del visor
                original_html = self.view.report_viewer.toHtml()
                self.view.report_viewer.setHtml(full_html)
                
                printer = QPrinter(QPrinter.HighResolution)
                printer.setOutputFormat(QPrinter.PdfFormat)
                printer.setOutputFileName(fileName)
                
                self.view.report_viewer.document().print_(printer)
                
                # Restaurar vista sin imagen
                self.view.report_viewer.setHtml(original_html)
                
                QMessageBox.information(self.view, "PDF Generado", f"Reporte guardado exitosamente en:\n{fileName}")
            except Exception as e:
                QMessageBox.critical(self.view, "Error", f"No se pudo generar el PDF:\n{str(e)}")