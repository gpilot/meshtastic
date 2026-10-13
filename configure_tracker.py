#!/usr/bin/env python3
"""Trace et re-application de la configuration "tracker" (capteur GPS branche) :
role TRACKER, position diffusee UNIQUEMENT sur le canal prive ExGP (jamais sur
Primary). Fonctionne sur n'importe quelle carte Meshtastic avec un GPS reel
branche - cette config utilise uniquement l'API Python standard, rien de
specifique au modele de carte.

Usage : python3 configure_tracker.py /dev/cu.usbmodemXXXX
(le port change a chaque reset USB natif - verifier avec `ls /dev/cu.usbmodem*`)

Points decouverts en debug, a connaitre avant de modifier ce script :
- Le device role et la position config sont lies : fixer `device.role` a
  TRACKER reapplique des valeurs par defaut de position config au reboot
  suivant (ca a ecrase position_broadcast_secs qu'on avait mis avant). D'ou
  l'ordre ici : role TRACKER + reboot, PUIS seulement la config position fine,
  pour ne pas se la faire ecraser.
- `position_broadcast_secs` a un minimum de 60 min (3600s) IMPOSE PAR LE
  FIRMWARE sur les canaux a cle publique/par defaut (Primary) - impossible a
  descendre en dessous, meme en reecrivant apres coup. Ce minimum NE
  S'APPLIQUE PAS a un canal secondaire avec sa propre cle (verifie
  empiriquement : 120s tient sur ExGP apres reboot).
- La visibilite de la position est controlee **par canal**, via
  `channel.settings.module_settings.position_precision` (0 a 32 bits, 0 =
  jamais envoyee sur ce canal, 32 = precision complete). Sur un canal a cle
  publique, le firmware plafonne lui-meme a 15 bits (~700m) quoi qu'on mette -
  pas la peine de forcer plus haut sur Primary. ExGP etant prive, pas de
  plafond : precision 32 directement.
- Pour une position FIXE (pas de GPS physique, ex. une gateway stationnaire) :
  utiliser `node.setFixedPosition(lat, lon, alt)` plutot que ce script (qui
  suppose un vrai capteur GPS branche et actif).
"""

import sys
import time

from meshtastic.serial_interface import SerialInterface
from meshtastic.protobuf import config_pb2

REGION = config_pb2.Config.LoRaConfig.RegionCode.EU_868
POSITION_BROADCAST_SECS = 120


def configure(port: str):
    iface = SerialInterface(port)
    time.sleep(2)
    node = iface.localNode

    # Region + role TRACKER d'abord (reboot necessaire avant la config
    # position fine, voir note en tete de fichier).
    node.localConfig.lora.region = REGION
    node.localConfig.lora.config_ok_to_mqtt = True
    node.writeConfig("lora")
    time.sleep(2)

    node.localConfig.device.role = config_pb2.Config.DeviceConfig.Role.TRACKER
    node.writeConfig("device")
    time.sleep(2)

    node.localConfig.position.gps_mode = config_pb2.Config.PositionConfig.GpsMode.ENABLED
    node.writeConfig("position")
    time.sleep(2)

    print("Role/region/GPS ecrits. Redemarrage intermediaire necessaire...")
    node.reboot()
    iface.close()

    time.sleep(15)  # le boot complet (sondage GPS inclus) prend ~35-40s de plus

    iface = SerialInterface(port)
    time.sleep(2)
    node = iface.localNode

    # Position : diffusion courte, uniquement sur ExGP.
    node.localConfig.position.position_broadcast_secs = POSITION_BROADCAST_SECS
    node.localConfig.position.position_broadcast_smart_enabled = True
    node.writeConfig("position")
    time.sleep(2)

    ch0 = node.channels[0]  # Primary : jamais de position dessus
    ch0.settings.module_settings.position_precision = 0
    node.writeChannel(0)
    time.sleep(2)

    ch1 = node.channels[1]  # ExGP : precision complete, canal prive
    ch1.settings.module_settings.position_precision = 32
    node.writeChannel(1)
    time.sleep(2)

    print("Configuration position ecrite. Redemarrage final...")
    node.reboot()
    iface.close()


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} /dev/cu.usbmodemXXXX")
        return 1
    configure(sys.argv[1])


if __name__ == "__main__":
    sys.exit(main())
