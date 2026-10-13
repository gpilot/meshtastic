#!/usr/bin/env python3
"""Trace et re-application de la configuration "gateway" : le device connecte en
WiFi qui pont le canal ExGP vers le broker MQTT (RabbitMQ). Fonctionne sur
n'importe quelle carte Meshtastic avec WiFi (ESP32-S3 : XIAO, Heltec V4, etc.) -
cette config utilise uniquement l'API Python standard, rien de specifique au
modele de carte.

Usage : python3 configure_gateway.py /dev/cu.usbmodemXXXX
(le port change a chaque reset USB natif - verifier avec `ls /dev/cu.usbmodem*`)
"""

import sys
import time
import base64

from meshtastic.serial_interface import SerialInterface
from meshtastic.protobuf import channel_pb2, config_pb2

from secrets import (
    CHANNEL_PSK_B64,
    WIFI_SSID,
    WIFI_PSK,
    MQTT_BROKER,
    MQTT_USERNAME,
    MQTT_PASSWORD,
    MQTT_ROOT,
)

REGION = config_pb2.Config.LoRaConfig.RegionCode.EU_868


def configure(port: str):
    iface = SerialInterface(port)
    time.sleep(2)
    node = iface.localNode

    # Region EU868 - obligatoire avant toute emission.
    node.localConfig.lora.region = REGION
    # Sans ce flag, les paquets que CE device origine portent le flag
    # DontMqttMeBro et ne sont jamais relayes vers MQTT, meme par une gateway
    # prete a le faire (bug trouve et corrige en debug - cause de "le message
    # n'arrive pas sur le broker" alors que tout le reste etait correct).
    node.localConfig.lora.config_ok_to_mqtt = True
    node.writeConfig("lora")
    time.sleep(2)

    # WiFi : necessaire pour que ce device puisse joindre le broker lui-meme
    # (pas de proxy via le telephone - connexion directe device -> broker).
    node.localConfig.network.wifi_enabled = True
    node.localConfig.network.wifi_ssid = WIFI_SSID
    node.localConfig.network.wifi_psk = WIFI_PSK
    node.writeConfig("network")
    time.sleep(2)

    # Module MQTT : pont vers RabbitMQ.
    node.moduleConfig.mqtt.enabled = True
    node.moduleConfig.mqtt.address = MQTT_BROKER
    node.moduleConfig.mqtt.username = MQTT_USERNAME
    node.moduleConfig.mqtt.password = MQTT_PASSWORD
    node.moduleConfig.mqtt.tls_enabled = True
    node.moduleConfig.mqtt.root = MQTT_ROOT
    node.writeConfig("mqtt")
    time.sleep(2)

    # Canal Primary (index 0) : surtout pas de pont MQTT dessus, on ne veut
    # remonter que le trafic prive ExGP, pas le bruit du mesh public.
    ch0 = node.channels[0]
    ch0.settings.uplink_enabled = False
    ch0.settings.downlink_enabled = False
    node.writeChannel(0)
    time.sleep(2)

    # Canal ExGP (index 1) : le seul a avoir uplink+downlink actives, c'est le
    # point de tout ce device.
    ch1 = node.channels[1]
    ch1.role = channel_pb2.Channel.Role.SECONDARY
    ch1.settings.name = "ExGP"
    ch1.settings.psk = base64.b64decode(CHANNEL_PSK_B64)
    ch1.settings.uplink_enabled = True
    ch1.settings.downlink_enabled = True
    node.writeChannel(1)
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
