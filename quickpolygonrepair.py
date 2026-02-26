# -----------------------------------------------------------------------------#
# Title:       QuickPolygonRepair                                              #
# Author:      Mike Elstermann (#geoObserver)                                  #
# Version:     v0.4                                                            #
# Created:     15.10.2025                                                      #
# Last Change: 26.02.2026                                                      #
# see also:    https://geoobserver.de/qgis-plugins/                            #
#                                                                              #
# This file contains code generated with assistance from an AI                 #
# No warranty is provided for AI-generated portions.                           #
# Human review and modification performed by: Mike Elstermann (#geoObserver)   #
# -----------------------------------------------------------------------------#

import os
import time
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QToolButton, QToolBar, QPushButton
from qgis.PyQt.QtGui import QIcon
from qgis.utils import iface
from qgis.core import (
    QgsMapLayer, QgsWkbTypes, edit,
    QgsGeometry, QgsFeature, QgsPointXY
)

plugin_dir = os.path.dirname(__file__)

# Qt5 / Qt6 Enum-Kompatibilität
try:
    # Qt6
    MSG_ICON_QUESTION = QMessageBox.Icon.Question
    MSG_ROLE_REJECT = QMessageBox.ButtonRole.RejectRole
    MSG_ROLE_NO = QMessageBox.ButtonRole.NoRole
    MSG_ROLE_YES = QMessageBox.ButtonRole.YesRole
except AttributeError:
    # Qt5
    MSG_ICON_QUESTION = QMessageBox.Question
    MSG_ROLE_REJECT = QMessageBox.RejectRole
    MSG_ROLE_NO = QMessageBox.NoRole
    MSG_ROLE_YES = QMessageBox.YesRole


class QuickPolygonRepair:
    def __init__(self, iface):
        self.iface = iface
        self.toolbar = None
        self.actions = []

    # Dialog
    def frage_nutzer(self, myText):
        # Parent setzen, damit das Dialog-Fenster modal zur QGIS-Hauptfenster ist
        parent = self.iface.mainWindow() if hasattr(self.iface, "mainWindow") else None
        msg_box = QMessageBox(parent)
        # Qt6: Enums sind verschachtelt; Icon.Question statt QMessageBox.Question
        msg_box.setIcon(MSG_ICON_QUESTION)
        msg_box.setWindowTitle("Try to repair?")
        msg_box.setText(myText)

        # Buttons hinzufügen (mit ButtonRole)
        btn_cancel = msg_box.addButton("cancel", MSG_ROLE_REJECT)
        btn_repair = msg_box.addButton("repair only", MSG_ROLE_NO)
        btn_repair_del = msg_box.addButton("repair + delete duplicate nodes", MSG_ROLE_YES)

        # Dialog anzeigen
        msg_box.exec()

        # Sicher prüfen, welche Schaltfläche geklickt wurde
        clicked = msg_box.clickedButton()
        if clicked == btn_cancel:
            return "cancel"
        elif clicked == btn_repair:
            return "repair"
        elif clicked == btn_repair_del:
            return "repair + delete"
        # Fallback
        return "cancel"

    def initGui(self):
        # Gemeinsame Toolbar finden oder anlegen
        self.toolbar = self.iface.mainWindow().findChild(QToolBar, "geoObserverTools")
        if not self.toolbar:
            self.toolbar = self.iface.addToolBar("geoObserverTools")
            self.toolbar.setObjectName("geoObserverTools")
            self.toolbar.setToolTip("geoObserver Tools ...")

        icon = os.path.join(plugin_dir, "logo.png")
        self.action = QAction(QIcon(icon), "QuickPolygonRepair", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.toolbar.addAction(self.action)
        self.actions.append(self.action)

    def unload(self):
        for action in self.actions:
            if self.toolbar:
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
        print(f"\n\n+--- S T A R T --- {formatted_time} -------------------------------")

        layer = self.iface.activeLayer()
        myMessage1 = (
            "No active polygon layer found,&nbsp;please activate one polygon layer."
        )

        if (
            not layer
            or layer.type() != QgsMapLayer.VectorLayer
            or QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PolygonGeometry
        ):
            try:
                self.iface.messageBar().pushWarning("QuickPolygonRepair", myMessage1)
            except Exception:
                self.iface.messageBar().pushMessage("QuickPolygonRepair", myMessage1)
            return

        if layer.isEditable():
            layer.commitChanges()

        valid_features = 0
        invalid_ids = []

        for feature in layer.getFeatures():
            geom = feature.geometry()
            valid_features += 1
            if not geom.isGeosValid():
                invalid_ids.append(feature.id())

        runtime = time.time() - starttime

        if invalid_ids:
            layer.selectByIds(invalid_ids)
            try:
                self.iface.messageBar().pushWarning(
                    "QuickPolygonRepair",
                    f"NotOK: {len(invalid_ids)} from {valid_features} polygons are not valid "
                    f"in layer '{layer.name()}' (detecttime: {round(runtime, 3)} sec.)",
                )
            except Exception:
                self.iface.messageBar().pushMessage(
                    "QuickPolygonRepair",
                    f"NotOK: {len(invalid_ids)} from {valid_features} polygons are not valid in layer '{layer.name()}'."
                )

            antwort = self.frage_nutzer(
                f"Sorry, in your layer <b style='color:#800000'>{layer.name()}</b><br>{len(invalid_ids)} from {valid_features} polygon(s) are <b>NOT valid</b>.<br><br>"
                "Try to repair? Please make a copy before!"
            )

            if antwort in ["repair", "repair + delete"]:
                print("| M5: Repairing ...")
                with edit(layer):
                    for fid in invalid_ids:
                        feature = QgsFeature(layer.getFeature(fid))
                        fixed_geom = feature.geometry().makeValid()
                        if fixed_geom and fixed_geom.isGeosValid():
                            layer.changeGeometry(fid, fixed_geom)

                try:
                    self.iface.messageBar().pushInfo(
                        "QuickPolygonRepair",
                        "Repair attempt completed. Please start a new test...",
                    )
                except Exception:
                    self.iface.messageBar().pushMessage("QuickPolygonRepair", "Repair attempt completed.")

                layer.removeSelection()

                if antwort == "repair + delete":
                    print("| M6: Deleting duplicate nodes ...")
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
                                    new_geom = QgsGeometry.fromPolygonXY(cleaned_polys[0])
                                elif len(cleaned_polys) > 1:
                                    new_geom = QgsGeometry.fromMultiPolygonXY(cleaned_polys)

                            elif ft == QgsWkbTypes.GeometryCollection:
                                collected_polys = []
                                for part in original_geom.constParts():
                                    part_clone = part.clone()
                                    part_geom = QgsGeometry(part_clone)
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

                                if len(collected_polys) == 1:
                                    new_geom = QgsGeometry.fromPolygonXY(collected_polys[0])
                                elif len(collected_polys) > 1:
                                    new_geom = QgsGeometry.fromMultiPolygonXY(collected_polys)

                            if new_geom and new_geom.isGeosValid() and not new_geom.equals(original_geom):
                                layer.changeGeometry(feature.id(), new_geom)

                    print("| M7: All duplicate points have been removed.")

            else:
                print("| M8: User cancelled.")
        else:
            print("| M9: All Polygons are valid, nothing to do.")
            try:
                self.iface.messageBar().pushInfo(
                    "QuickPolygonRepair",
                    f"OK: All {valid_features} polygons in layer '{layer.name()}' are valid "
                    f"(runtime: {round(runtime, 3)} sec.)",
                )
            except Exception:
                self.iface.messageBar().pushMessage("QuickPolygonRepair", "All polygons are valid.")

        endtime = time.time()
        formatted_time = time.strftime("%H:%M:%S", time.localtime(endtime))
        print(f"+--- E N D ------- {formatted_time} -------------------------------")
        