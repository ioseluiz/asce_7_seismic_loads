import sys
from PyQt5.QtWidgets import QApplication
from model import SeismicModel
from view import SeismicView
from controller import SeismicController

def main():
    # Inicializar aplicación Qt
    app = QApplication(sys.argv)
    
    # Instanciar MVC
    model = SeismicModel()
    view = SeismicView()
    controller = SeismicController(model, view)
    
    # Mostrar ventana
    view.show()
    
    # Loop de eventos
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()