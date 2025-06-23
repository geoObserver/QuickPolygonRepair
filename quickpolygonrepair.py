import os
from PyQt5.QtWidgets import QAction, QMessageBox
from PyQt5.QtGui import QIcon
from qgis.core import QgsRasterLayer, QgsProject, QgsMapLayer, QgsCoordinateReferenceSystem, QgsWkbTypes, edit
from qgis.utils import iface
import time
from qgis.PyQt.QtCore import QVariant

plugin_dir = os.path.dirname(__file__)

class QuickPolygonRepair:
    def __init__(self, iface):
        self.iface = iface

    # Funktion zur Anzeige der Abfrage
    def frage_nutzer(self,myText):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("Repair?")
        msg_box.setText(myText)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No )
        msg_box.setDefaultButton(QMessageBox.Yes)
        antwort = msg_box.exec_()

        if antwort == QMessageBox.Yes:
            #print("Benutzer hat 'Ja' gewählt.")
            return "yes"
        elif antwort == QMessageBox.No:
            #print("Benutzer hat 'Nein' gewählt.")
            return "no"
#        elif antwort == QMessageBox.Cancel:
#            print("Benutzer hat 'Abbrechen' gewählt.")
#            return "abbrechen"

    def initGui(self):
        # Create an action (i.e. a button) with Logo
        icon = os.path.join(os.path.join(plugin_dir, 'logo.png'))
        self.action = QAction(QIcon(icon), 'QuickPolygonRepair', self.iface.mainWindow())
        # Add the action to the toolbar
        self.iface.addToolBarIcon(self.action)
        # Connect the run() method to the action
        self.action.triggered.connect(self.run)
      
    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        del self.action

    def run(self):
        layer = iface.activeLayer()
        #print("1. layer:  {layer}")
        
        myMessage1 = f"No active polygon layer found,{'&nbsp;' * 1}please activate one polygon layer."
        
        if not layer:
            self.iface.messageBar().pushMessage("QuickPolygonRepair", myMessage1, 1, 3)
            #print("2. layer:  {layer}")
            return

        if layer.type() != QgsMapLayer.VectorLayer:
            self.iface.messageBar().pushMessage("QuickPolygonRepair", myMessage1, 1, 3)
            #print("3. layer: {layer}")
            return
                 
        if layer.isEditable():
            layer.commitChanges()
            #print("Editing mode ended.")
            
        valid_features = 0
        starttime = time.time()
        selected_layers = iface.layerTreeView().selectedLayers()
        #print(selected_layers)
        anzahl = len(selected_layers)
        #print(f"number of active (selected) layers: {anzahl}")
        if anzahl != 1:
            #print ('Number not equal to 1')
            self.iface.messageBar().pushMessage("QuickPolygonRepair", 'Only one polygon layer can be active.',1,3)
            return
        if layer:
            geometry_type = QgsWkbTypes.geometryType(layer.wkbType())
            if geometry_type == QgsWkbTypes.PolygonGeometry:
                print("Polygon layer detected.")
            else:
                print("No polygon layer detected.")
                self.iface.messageBar().pushMessage("QuickPolygonRepair", 'Your layer is not a polygon layer.',1,3)
                return    

        if not layer:
            #print("No active layer found.")
            self.iface.messageBar().pushMessage("QuickPolygonRepair", 'No active layer found.',1,3)
        else:
            layer.removeSelection()
            invalid_ids = []

            for feature in layer.getFeatures():
                geom = feature.geometry()
                valid_features = valid_features + 1
                if not geom.isGeosValid():
                    invalid_ids.append(feature.id())
                    
            endtime = time.time()
            runtime = endtime - starttime

            if invalid_ids:
                layer.selectByIds(invalid_ids)
                #print(f"{len(invalid_ids)} not valid polygons selected.")
                self.iface.messageBar().pushMessage("QuickPolygonRepair", 'NotOK: ' + str(len(invalid_ids))+' from ' + str(valid_features) + ' polygons are not valid in layer "' + layer.name() + '" (runtime: ' + str(round(runtime,3)) + ' sec.).',1,3)
                antwort = self.frage_nutzer('Try to repair the ' + str(len(invalid_ids))+' not valid polygon(s)? \nPlease make a copy before!')
                print(antwort)
                if antwort == 'yes':
                    #self.iface.messageBar().pushMessage('Try to repair ' + str(len(invalid_ids))+' polygons ...',1,3)
                    for fid in invalid_ids:
                        feature = layer.getFeature(fid)
                        fixed_geom = feature.geometry().makeValid()
                        if fixed_geom.isGeosValid():
                            with edit(layer):
                                layer.changeGeometry(fid, fixed_geom)
                    self.iface.messageBar().pushMessage("QuickPolygonRepair", f"Repair attempt completed,{'&nbsp;' * 1}please start a new test ...",3,3)
                    layer.removeSelection()
            else:
                #print("All geometries are valid.")
                self.iface.messageBar().pushMessage("QuickPolygonRepair", 'OK: All ' + str(valid_features) + ' polygons in layer "' + layer.name() + '" are valid (runtime: ' + str(round(runtime,3)) + ' sec.).',3,3)
                


