#!/usr/bin/env python3
"""Script compagnon pour un noeud Meshtastic (firmware stock, pas de modification
firmware) : ecoute les messages recus sur le mesh, et envoie un message texte fixe
a intervalle regulier sur le canal indique.

Le firmware Meshtastic stock n'a pas de moteur de script pour automatiser un envoi
periodique - ce role est assure ici par ce script, via l'API serie Meshtastic.

Usage : python3 listen_and_send.py /dev/cu.usbmodemXXXX [canal_index]
(canal_index par defaut : 0 = Primary. Utiliser 1 pour ExGP.)
"""

import sys
import time

from pubsub import pub
from meshtastic.serial_interface import SerialInterface

SEND_INTERVAL_S = 5 * 60
MESSAGE = "Hello Luc J."


def on_receive(packet, interface):
    decoded = packet.get("decoded", {})
    if decoded.get("portnum") != "TEXT_MESSAGE_APP":
        return
    sender = packet.get("fromId", "?")
    channel = packet.get("channel", 0)
    text = decoded.get("text", "")
    print(f"[recu, canal {channel}] {sender}: {text}")


def main():
    if len(sys.argv) not in (2, 3):
        print(f"Usage: {sys.argv[0]} /dev/cu.usbmodemXXXX [canal_index]")
        print("(le port change a chaque reset USB natif - verifier avec `ls /dev/cu.usbmodem*`)")
        return 1

    port = sys.argv[1]
    channel_index = int(sys.argv[2]) if len(sys.argv) == 3 else 0

    interface = SerialInterface(port)
    pub.subscribe(on_receive, "meshtastic.receive")
    print(f"Ecoute du mesh demarree. Envoi programme toutes les 5 minutes sur le canal index {channel_index}.")

    last_send = 0.0
    try:
        while True:
            now = time.time()
            if now - last_send >= SEND_INTERVAL_S:
                interface.sendText(MESSAGE, channelIndex=channel_index)
                print(f"[envoye, canal {channel_index}] {MESSAGE}")
                last_send = now
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArret demande.")
    finally:
        interface.close()


if __name__ == "__main__":
    sys.exit(main())
