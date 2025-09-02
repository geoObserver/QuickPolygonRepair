import os
import time
from PyQt5.QtWidgets import QAction, QMessageBox, QPushButton, QToolBar
from PyQt5.QtGui import QIcon
from qgis.utils import iface
from qgis.core import (
    QgsMapLayer, QgsWkbTypes, edit,
    QgsGeometry, QgsFeature, QgsPointXY
)

plugin_dir = os.path.dirname(__file__)

class QuickPolygonRepair:
    def __init__(self, iface):
        self.iface = iface
        self.toolbar = None
        self.actions = []

    # Dialog
    def frage_nutzer(self, myText):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("Repair?")
        msg_box.setText(myText)

        button0 = QPushButton("cancel ")
        button1 = QPushButton("repair only")
        button2 = QPushButton("repair + delete duplicate nodes")
        msg_box.addButton(button0, QMessageBox.RejectRole)
        msg_box.addButton(button1, QMessageBox.NoRole)
        msg_box.addButton(button2, QMessageBox.YesRole)
        antwort = msg_box.exec_()

        if antwort == 0:
            return "cancel"
        elif antwort == 1:
            return "repair"
        elif antwort == 2:
            return "repair + delete"

    def initGui(self):
        self.toolbar = self.iface.mainWindow().findChild(QToolBar, "#geoObserverTools")
        if not self.toolbar:
            self.toolbar = self.iface.addToolBar("#geoObserver Tools")
            self.toolbar.setObjectName("#geoObserverTools")

        icon = os.path.join(plugin_dir, 'logo.png')
        self.action = QAction(QIcon(icon), 'QuickPolygonRepair', self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.toolbar.addAction(self.action)
        self.actions.append(self.action)

    def unload(self):
        for action in self.actions:
            self.toolbar.removeAction(action)
        self.actions.clear()

    # Hilfsfunktion: Duplikate in einem Ring entfernen (Ring = Liste[QgsPointXY])
    def remove_duplicate_points(self, ring):
        seen = set()
        cleaned = []
        # letzten Punkt (Schließpunkt) beim Iterieren auslassen
        for pt in ring[:-1]:
            key = (round(pt.x(), 8), round(pt.y(), 8))
            if key not in seen:
                seen.add(key)
                cleaned.append(pt)
        # wieder schließen, wenn möglich
        if cleaned and cleaned[0] != cleaned[-1]:
            cleaned.append(cleaned[0])
        return cleaned

    # Hilfsfunktion: Ringsammlung säubern, zu kurze Ringe verwerfen
    def clean_rings(self, rings):
        cleaned = []
        for r in rings:
            cr = self.remove_duplicate_points(r)
            if len(cr) >= 4:
                cleaned.append(cr)
        return cleaned

    def run(self):
        starttime = time.time()
        formatted_time = time.strftime("%H:%M:%S", time.localtime(starttime))
        print('\n\n+--- S T A R T --- ' + str(formatted_time) + ' -------------------------------')

        layer = self.iface.activeLayer()
        myMessage1 = f"No active polygon layer found,{'&nbsp;' * 1}please activate one polygon layer."

        if not layer or layer.type() != QgsMapLayer.VectorLayer or QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PolygonGeometry:
            self.iface.messageBar().pushMessage("QuickPolygonRepair: ", myMessage1, 1, 3)
            return

        if layer.isEditable():
            layer.commitChanges()

        valid_features = 0
        invalid_ids = []

        # 1) Ungültige Geometrien auflisten
        for feature in layer.getFeatures():
            geom = feature.geometry()
            valid_features += 1
            if not geom.isGeosValid():
                invalid_ids.append(feature.id())

        runtime = time.time() - starttime

        if invalid_ids:
            layer.selectByIds(invalid_ids)
            self.iface.messageBar().pushMessage(
                "QuickPolygonRepair: ",
                f"NotOK: {len(invalid_ids)} from {valid_features} polygons are not valid in layer '{layer.name()}' "
                f"(detecttime: {round(runtime, 3)} sec.).",
                1, 3
            )
            antwort = self.frage_nutzer(
                f"Sorry, {len(invalid_ids)} from {valid_features} polygon(s) are NOT valid.\n"
                f"Try to repair? Please make a copy before!"
            )

            if antwort in ["repair", "repair + delete"]:
                print('| M5: Repairing ...')
                with edit(layer):
                    for fid in invalid_ids:
                        feature = QgsFeature(layer.getFeature(fid))
                        fixed_geom = feature.geometry().makeValid()
                        # makeValid kann MultiPolygon/Polygon liefern, selten auch Collections mit Polygonen+Rest
                        if fixed_geom and fixed_geom.isGeosValid():
                            layer.changeGeometry(fid, fixed_geom)

                self.iface.messageBar().pushMessage(
                    "QuickPolygonRepair: ",
                    "Repair attempt completed. Please start a new test...",
                    3, 3
                )
                layer.removeSelection()

                # 2) Optional: Duplikatknoten entfernen – robust & ohne addPart-Spielchen
                if antwort == "repair + delete":
                    print('| M6: Deleting duplicate nodes ...')
                    with edit(layer):
                        for feature in layer.getFeatures():
                            original_geom = feature.geometry()
                            if original_geom.isNull():
                                continue

                            new_geom = None
                            ft = QgsWkbTypes.flatType(original_geom.wkbType())

                            if ft == QgsWkbTypes.Polygon:
                                rings = original_geom.asPolygon()
                                cleaned_rings = self.clean_rings(rings)
                                if cleaned_rings:
                                    new_geom = QgsGeometry.fromPolygonXY(cleaned_rings)

                            elif ft == QgsWkbTypes.MultiPolygon:
                                polys = original_geom.asMultiPolygon()
                                cleaned_polys = []
                                for poly in polys:
                                    cr = self.clean_rings(poly)
                                    if cr:
                                        cleaned_polys.append(cr)
                                if len(cleaned_polys) == 1:
                                    # Wenn nur ein Polygon übrig bleibt, Polygon statt MultiPolygon setzen
                                    new_geom = QgsGeometry.fromPolygonXY(cleaned_polys[0])
                                elif len(cleaned_polys) > 1:
                                    new_geom = QgsGeometry.fromMultiPolygonXY(cleaned_polys)

                            elif ft == QgsWkbTypes.GeometryCollection:
                                # Nur Polygonteile extrahieren (sicher klonen!)
                                collected_polys = []
                                for part in original_geom.constParts():
                                    part_clone = part.clone()               # <— tiefe Kopie (vermeidet Crash)
                                    part_geom = QgsGeometry(part_clone)     # als QgsGeometry „einwickeln“
                                    pft = QgsWkbTypes.flatType(part_geom.wkbType())

                                    if pft == QgsWkbTypes.Polygon:
                                        rings = part_geom.asPolygon()
                                        cr = self.clean_rings(rings)
                                        if cr:
                                            collected_polys.append(cr)

                                    elif pft == QgsWkbTypes.MultiPolygon:
                                        for poly in part_geom.asMultiPolygon():
                                            cr = self.clean_rings(poly)
                                            if cr:
                                                collected_polys.append(cr)

                                # aus gesammelten Polygonen wieder Polygon/MultiPolygon erzeugen
                                if len(collected_polys) == 1:
                                    new_geom = QgsGeometry.fromPolygonXY(collected_polys[0])
                                elif len(collected_polys) > 1:
                                    new_geom = QgsGeometry.fromMultiPolygonXY(collected_polys)

                            # Nur schreiben, wenn sinnvoll
                            if new_geom and new_geom.isGeosValid() and not new_geom.equals(original_geom):
                                layer.changeGeometry(feature.id(), new_geom)

                    print("| M7: All duplicate points have been removed.")

            else:
                print('| M8: User cancelled.')
        else:
            print('| M9: All Polygons are valid, nothing to do.')
            self.iface.messageBar().pushMessage(
                "QuickPolygonRepair: ",
                f"OK: All {valid_features} polygons in layer '{layer.name()}' are valid "
                f"(runtime: {round(runtime, 3)} sec.).",
                3, 3
            )

        endtime = time.time()
        formatted_time = time.strftime("%H:%M:%S", time.localtime(endtime))
        print('+--- E N D ------- ' + str(formatted_time) + ' -------------------------------')
