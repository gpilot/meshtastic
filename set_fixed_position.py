#!/usr/bin/env python3
"""Fixe une position GPS statique sur un device qui n'a pas de capteur GPS
physique (ex. une gateway stationnaire). Utilise `node.setFixedPosition()`, qui
gere a la fois l'ecriture de la position et l'activation du flag
`fixed_position` en un seul message admin.

Usage : python3 set_fixed_position.py /dev/cu.usbmodemXXXX <lat> <lon> [alt_m]

Note observee en usage reel : apres avoir fixe la position via ce script, evite
d'aller dans l'app > Reglages/Position pour "juste verifier" - cet ecran a
semble bugger et pousser a supprimer la position (repassant fixed_position a
False). Verifier plutot via la carte ou la fiche du noeud dans l'app, qui
affichent la position sans passer par cet ecran d'edition.
"""

import sys
import time

from meshtastic.serial_interface import SerialInterface


def main():
    if len(sys.argv) not in (4, 5):
        print(f"Usage: {sys.argv[0]} /dev/cu.usbmodemXXXX <lat> <lon> [alt_m]")
        return 1

    port = sys.argv[1]
    lat = float(sys.argv[2])
    lon = float(sys.argv[3])
    alt = int(sys.argv[4]) if len(sys.argv) == 5 else 0

    iface = SerialInterface(port)
    time.sleep(2)
    node = iface.localNode
    node.setFixedPosition(lat, lon, alt)
    time.sleep(3)
    iface.close()
    print(f"Position fixee : {lat}, {lon}" + (f", {alt}m" if alt else ""))


if __name__ == "__main__":
    sys.exit(main())
