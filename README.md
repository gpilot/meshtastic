# Meshtastic - outillage de provisioning

Outils pour flasher et configurer des cartes ESP32-S3 sous firmware Meshtastic
stock (pas de firmware custom), formant un mesh prive sur un canal chiffre
**ExGP**, avec un pont vers un broker MQTT (RabbitMQ) pour un device "gateway".

**Les scripts Python de ce dossier sont independants du modele de carte** : ils
utilisent l'API serie standard du paquet `meshtastic`, qui parle a n'importe
quel device Meshtastic de la meme facon. Seul le **flashage initial** depend du
modele exact (cible firmware, offsets de partition) - voir plus bas.

## Installation

```bash
pip install -r requirements.txt
cp secrets.py.example secrets.py   # puis renseigner les vraies valeurs
```

`secrets.py` n'est jamais committe (voir `.gitignore`).

## Roles

Un meme device ne cumule qu'un seul de ces roles a la fois :

- **`configure_gateway.py`** : connecte en WiFi, porte le module MQTT de
  Meshtastic, ponte le canal ExGP vers le broker RabbitMQ. Seul role avec
  `uplink_enabled`/`downlink_enabled` actifs sur ExGP, et WiFi + MQTT
  configures.
- **`configure_participant.py`** : simple membre du mesh sur ExGP (envoie/
  recoit via LoRa), aucun pont MQTT, pas de WiFi.
- **`configure_tracker.py`** : capteur GPS reel branche, role device `TRACKER`,
  diffuse sa position uniquement sur ExGP (jamais sur Primary - voir
  commentaires du script pour le detail des pieges rencontres en debug).
- **`set_fixed_position.py`** : pour un device SANS GPS physique (ex. une
  gateway stationnaire) qui doit quand meme annoncer une position fixe.

```bash
python3 configure_gateway.py     /dev/cu.usbmodemXXXX
python3 configure_participant.py /dev/cu.usbmodemXXXX
python3 configure_tracker.py     /dev/cu.usbmodemXXXX
python3 set_fixed_position.py    /dev/cu.usbmodemXXXX 43.628340 7.076488
```

Ces scripts utilisent l'API Python directe de `meshtastic` (`SerialInterface` +
`localNode.writeConfig(...)`), pas le CLI `meshtastic --set` : des changements
via le CLI ont pu etre confirmes en sortie mais ne pas persister reellement
apres reboot sur ce firmware, sans message d'erreur. L'API directe s'est
montree fiable a chaque test.

## Points importants decouverts en debug

- **`lora.config_ok_to_mqtt`** doit etre `true` sur l'**emetteur** (pas
  seulement sur la gateway) pour que ses paquets soient relayables vers MQTT -
  sinon ils portent un flag `DontMqttMeBro` et sont silencieusement ignores par
  la gateway, meme correctement configuree.
- **`position_broadcast_secs`** a un minimum de 60 minutes impose par le
  firmware sur les canaux a cle publique/par defaut (Primary) - impossible a
  descendre en dessous. Ce minimum ne s'applique pas a un canal secondaire avec
  sa propre cle (verifie empiriquement sur ExGP).
- **Visibilite de la position par canal** : `channel.settings.module_settings.
  position_precision` (0-32 bits) controle si/avec quelle precision la
  position est partagee sur CE canal. Sur un canal a cle publique, le firmware
  plafonne lui-meme a 15 bits (~700m), quoi qu'on mette - protection vie privee
  automatique.
- **La frequence radio** est fixee par un hash du nom du canal **Primary**
  uniquement (pas des canaux secondaires) - tous les canaux d'un device
  partagent la meme frequence, la separation entre canaux est purement
  logique/chiffrement, pas radio.
- **`fixed_position`** fixee via l'API admin peut sembler "buguer" dans l'app
  (ecran Reglages/Position) - verifier plutot via la carte ou la fiche du
  noeud, qui n'ont pas ce souci.

## Flasher le firmware Meshtastic stock

Ceci depend du modele exact de carte - pas besoin de PlatformIO, le firmware
officiel se flashe tel quel avec `esptool` depuis les binaires GitHub.

### 1. Identifier la carte exacte

```bash
esptool --port /dev/cu.usbmodemXXXX chip-id
```

Note la taille de PSRAM annoncee (`Embedded PSRAM ...`) - elle permet de
distinguer les variantes d'une meme famille (ex. Heltec V4 "simple" 2MB vs "R8"
8MB), dont les cibles firmware different.

### 2. Telecharger le bundle firmware correspondant a la puce

Les releases Meshtastic sont groupees par famille de puce, pas par carte
individuelle :

```bash
curl -sL -o firmware-esp32s3.zip \
  "https://github.com/meshtastic/firmware/releases/download/v2.7.26.54e0d8d/firmware-esp32s3-2.7.26.54e0d8d.zip"
```

(Remplacer la version par la derniere release stable si besoin -
`https://api.github.com/repos/meshtastic/firmware/releases/latest`.)

### 3. Trouver la cible exacte et ses offsets de partition

Chaque carte a un fichier `.mt.json` dans le zip qui donne son nom de cible
(`platformioTarget`) et sa table de partitions complete (champ `part`, offsets
reels). Ne jamais deviner ces offsets a la main - ils varient selon la taille
de flash/PSRAM. Exemples verifies :

| Carte | Cible | app0 (offset) | spiffs (offset) |
|---|---|---|---|
| Heltec V4 (2MB PSRAM) | `heltec-v4` | `0x10000` | `0xc90000` |
| XIAO ESP32-S3 + Wio-SX1262 | `seeed-xiao-s3` | `0x10000` | `0x670000` |

### 4. Flasher

Le `.factory.bin` contient bootloader + table de partitions + application en un
seul bloc (flash complet depuis une carte vierge), a ecrire a l'offset `0x0`. Le
`littlefs-*.bin` est le systeme de fichiers separe, a ecrire a son offset
`spiffs` :

```bash
unzip firmware-esp32s3.zip firmware-<cible>-*.factory.bin littlefs-<cible>-*.bin

esptool --port /dev/cu.usbmodemXXXX write_flash \
  0x0        firmware-<cible>-<version>.factory.bin \
  <offset>   littlefs-<cible>-<version>.bin
```

Verifier que le firmware a correctement redemarre (pas juste que l'ecriture a
reussi - sur ESP32-S3 a USB natif, un `esptool` trop ancien peut laisser la
carte bloquee en mode bootloader apres le flash) :

```bash
meshtastic --port /dev/cu.usbmodemXXXX --info
```

Si ca timeout en boucle, mettre a jour esptool (`pip install --upgrade esptool`,
v5+) et redeclencher un reset propre (`esptool --port ... --after hard_reset
run`), ou debrancher/rebrancher physiquement en dernier recours.

## Autres outils

- **`listen_and_send.py <port> [canal_index]`** : ecoute un canal et y envoie
  un message fixe toutes les 5 minutes (defaut : canal 0/Primary ; utiliser `1`
  pour ExGP).
- **`decode_mqtt.py`** : se connecte directement au broker MQTT, s'abonne a
  `msh/EU_868/2/e/ExGP/#`, et dechiffre en direct les messages recus (parsing
  `ServiceEnvelope` protobuf + AES-256-CTR avec la cle du canal - le nonce est
  reconstruit exactement comme le firmware, voir les commentaires du fichier).
  Decode les messages texte et les positions GPS lisiblement.
