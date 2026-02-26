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

from .quickpolygonrepair import QuickPolygonRepair

def classFactory(iface):
    return QuickPolygonRepair(iface)