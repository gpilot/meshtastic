#!/usr/bin/env python3
"""Trace et re-application de la configuration "participant" : simple membre du
mesh sur le canal ExGP, aucun role de pont MQTT (c'est configure_gateway.py qui
tient ce role sur un autre device). Fonctionne sur n'importe quelle carte
Meshtastic (ESP32-S3 : XIAO, Heltec V4, etc.) - cette config utilise uniquement
l'API Python standard, rien de specifique au modele de carte.

Usage : python3 configure_participant.py /dev/cu.usbmodemXXXX
(le port change a chaque reset USB natif - verifier avec `ls /dev/cu.usbmodem*`)
"""

import sys
import time
import base64

from meshtastic.serial_interface import SerialInterface
from meshtastic.protobuf import channel_pb2, config_pb2

from secrets import CHANNEL_PSK_B64

REGION = config_pb2.Config.LoRaConfig.RegionCode.EU_868


def configure(port: str):
    iface = SerialInterface(port)
    time.sleep(2)
    node = iface.localNode

    # Region EU868 - obligatoire avant toute emission.
    node.localConfig.lora.region = REGION
    # Sans ce flag, les paquets que CE device origine ne sont jamais relayes
    # vers MQTT par la gateway, meme si elle est prete a le faire.
    node.localConfig.lora.config_ok_to_mqtt = True
    node.writeConfig("lora")
    time.sleep(2)

    # Canal ExGP : pour envoyer/recevoir sur le mesh. Uplink/downlink a False
    # ici - ce device ne porte aucun pont MQTT, c'est le role de la gateway.
    ch = node.channels[1]
    ch.role = channel_pb2.Channel.Role.SECONDARY
    ch.settings.name = "ExGP"
    ch.settings.psk = base64.b64decode(CHANNEL_PSK_B64)
    ch.settings.uplink_enabled = False
    ch.settings.downlink_enabled = False
    node.writeChannel(1)
    time.sleep(2)

    # Explicitement desactives (idempotent, meme si deja off par defaut) -
    # aucun role de pont MQTT sur ce device.
    node.moduleConfig.mqtt.enabled = False
    node.writeConfig("mqtt")
    time.sleep(2)
    node.localConfig.network.wifi_enabled = False
    node.writeConfig("network")
    time.sleep(2)

    print("Configuration ecrite. Redemarrage...")
    node.reboot()
    iface.close()


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} /dev/cu.usbmodemXXXX")
        return 1
    configure(sys.argv[1])


if __name__ == "__main__":
    sys.exit(main())
