#!/usr/bin/env python3
"""Se connecte au broker MQTT, s'abonne au topic du canal ExGP, et dechiffre en
direct les messages recus (ServiceEnvelope protobuf + AES-256-CTR avec la cle du
canal).

Nonce AES-CTR reconstruit exactement comme le firmware (CryptoEngine::initNonce) :
8 octets packet_id (little-endian) + 4 octets from_node (little-endian) + 4 octets
a zero.
"""

import sys
import base64
from datetime import datetime

import paho.mqtt.client as mqtt
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from meshtastic.protobuf import mqtt_pb2, mesh_pb2, portnums_pb2

from secrets import CHANNEL_PSK_B64, MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, MQTT_ROOT

TOPIC = f"{MQTT_ROOT}/2/e/ExGP/#"


def decrypt_packet(packet: mesh_pb2.MeshPacket, psk: bytes) -> bytes:
    packet_id = packet.id
    from_node = getattr(packet, "from")
    nonce = packet_id.to_bytes(8, "little") + from_node.to_bytes(4, "little") + b"\x00" * 4

    cipher = Cipher(algorithms.AES(psk), modes.CTR(nonce))
    decryptor = cipher.decryptor()
    return decryptor.update(packet.encrypted) + decryptor.finalize()


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Connecte au broker ({reason_code}). Abonnement a {TOPIC}...")
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    psk = userdata
    envelope = mqtt_pb2.ServiceEnvelope()
    try:
        envelope.ParseFromString(msg.payload)
    except Exception as e:
        print(f"[{msg.topic}] Impossible de parser le ServiceEnvelope : {e}")
        return

    packet = envelope.packet
    from_node = getattr(packet, "from")
    received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{received_at}] [{msg.topic}]")
    print(f"  gateway: {envelope.gateway_id}  from: !{from_node:08x}  id: {packet.id}")

    if not packet.HasField("encrypted"):
        print("  (paquet non chiffre, rien a dechiffrer)")
        return

    try:
        plaintext = decrypt_packet(packet, psk)
        data = mesh_pb2.Data()
        data.ParseFromString(plaintext)
    except Exception as e:
        print(f"  Echec du dechiffrement (mauvaise cle ?) : {e}")
        return

    portnum_name = portnums_pb2.PortNum.Name(data.portnum)
    if data.portnum == portnums_pb2.PortNum.TEXT_MESSAGE_APP:
        print(f"  [{portnum_name}] {data.payload.decode('utf-8', errors='replace')}")
    elif data.portnum == portnums_pb2.PortNum.POSITION_APP:
        pos = mesh_pb2.Position()
        pos.ParseFromString(data.payload)
        lat = pos.latitude_i * 1e-7
        lon = pos.longitude_i * 1e-7
        print(f"  [{portnum_name}] lat={lat}, lon={lon}, alt={pos.altitude}m")
    else:
        print(f"  [{portnum_name}] payload (hex): {data.payload.hex()}")


def main():
    psk = base64.b64decode(CHANNEL_PSK_B64)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata=psk)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.tls_set()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_forever()


if __name__ == "__main__":
    sys.exit(main())
