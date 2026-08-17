# Tesla LoadPilot — firmware ESPHome : les deux nœuds, expliqués et généricisés

> Les extraits ci-dessous sont GÉNÉRICISÉS : broches, limites et IP passent en
> `substitutions`, tous les secrets en `!secret` (voir
> `90_SECRETS_A_REGENERER.md`). Les fichiers vivants de Loupiac contiennent
> des valeurs en clair — ne JAMAIS les copier tels quels.

## 1. Nœud téléinfo (`teleinfo-node.yaml`, Olimex ESP32-POE + hat Hallard)

### 1.1 Rôle
Décoder la TIC Linky mode standard et servir les 6 grandeurs utiles au DPM
(IRMS1-3, SINSTS1-3) sur DEUX canaux : entités HA (dashboards, package) et
diffusion UDP directe vers le nœud borne (latence).

### 1.2 Squelette généricisé

```yaml
substitutions:
  tic_rx_pin: GPIO36          # hat Hallard WeMos TeleInfo
  udp_port: "18511"

esphome:
  name: teleinfo-node
  compile_process_limit: 1    # 2 builds ESPHome simultanés = crash machine vécu

esp32:
  board: esp32-poe            # Olimex ESP32-POE (id PlatformIO dédié)
  framework: { type: arduino }

logger:
  baud_rate: 0                # l'UART0 n'est pas utilisé pour les logs

api:
  encryption: { key: !secret api_key_teleinfo }
ota:
  platform: esphome
  password: !secret ota_pwd_teleinfo

ethernet:                     # LAN8720 de l'ESP32-POE
  type: LAN8720
  mdc_pin: GPIO23
  mdio_pin: GPIO18
  clk_mode: GPIO17_OUT
  phy_addr: 0
  power_pin: GPIO12           # alimentation du PHY — voir note ci-dessous

uart:
  id: uart_bus
  rx_pin: ${tic_rx_pin}
  rx_buffer_size: 1024        # ⚠️ CRUCIAL, voir 1.3
  baud_rate: 9600
  parity: EVEN
  data_bits: 7
  stop_bits: 1

teleinfo:
  id: esp_teleinfo
  uart_id: uart_bus
  update_interval: 1s         # la boucle DPM veut une mesure fraîche
  historical_mode: false      # TIC mode STANDARD
```

**Note Ethernet ESP32-POE (réconciliation).** La config de PRODUCTION de
Loupiac tourne avec `board: esp32dev` et SANS `power_pin` — et l'Ethernet
fonctionne sur cet exemplaire (le brochage MDC 23 / MDIO 18 /
CLK `GPIO17_OUT` / phy 0 est bien celui de l'ESP32-POE). La config de
RÉFÉRENCE Olimex/ESPHome pour cette carte inclut `power_pin: GPIO12` : c'est
le GPIO qui alimente le PHY LAN8720. Sans lui, on dépend de l'état par
défaut de GPIO12 au boot — ça « marche » souvent, mais le PHY ne peut pas
être remis sous tension proprement et certains exemplaires/révisions ne
relancent pas l'Ethernet après un soft-reset. La version publiée déclare
donc le `power_pin` (inoffensif là où ça marchait déjà sans).

### 1.3 Pièges mesurés côté TIC

- **`rx_buffer_size: 1024` obligatoire en Tempo standard.** Une trame TIC
  standard Tempo dépasse 400 octets ; à 256 le buffer débordait
  (« Internal buffer full ») et ~2 trames sur 3 étaient perdues → cadence
  effective ~15 s qui faisait **pomper le DPM de la borne**.
- **Deux chemins dissociés pour les puissances** (astuce anti-recorder) :
  le capteur SINSTS de base est `internal: true` SANS throttle (c'est lui que
  lit `packet_transport`, ~1 Hz) ; une **copie** (`platform: copy`) throttlée
  2 s porte le `name:` → l'entité HA garde le même entity_id et le volume
  recorder ne bouge pas. Les courants IRMS restent à 1 s (entrée principale
  du DPM).
- **Filtre plancher sur IRMS** (bruit du capteur à vide) : `x ≤ 1.05 → 0`.
- Le registre **STGE** (text_sensor) est décodé côté HA : bit 7 =
  « dépassement de la puissance de référence EN COURS » constaté par le
  Linky lui-même — c'est le signal d'escalade du package.

### 1.4 Diffusion UDP directe (packet_transport)

```yaml
udp:
  id: udp_linky
#  addresses: ["<IP_NOEUD_BORNE>"]  # unicast si le broadcast LAN→WLAN est bloqué

packet_transport:
  - platform: udp
    udp_id: udp_linky
    update_interval: 1s              # re-diffusion COMPLÈTE = heartbeat
    encryption: !secret udp_linky_key   # XXTEA, clé hachée SHA-256
    rolling_code_enable: true        # anti-rejeu (persisté en flash, usure nulle)
    sensors:
      - { id: linky_irms1,  broadcast_id: lky_ia }
      - { id: linky_irms2,  broadcast_id: lky_ib }
      - { id: linky_irms3,  broadcast_id: lky_ic }
      - { id: linky_sinsts1, broadcast_id: lky_pa }
      - { id: linky_sinsts2, broadcast_id: lky_pb }
      - { id: linky_sinsts3, broadcast_id: lky_pc }
```

Points de conception (vérifiés dans les sources ESPHome, branche release) :
- tout **changement de valeur part immédiatement** (paquet incrémental dans
  la boucle suivante) EN PLUS du resend complet 1 Hz ;
- `broadcast_id` courts → paquet ~120 octets, ≤ 2 paquets/s ;
- chiffrement XXTEA : sans la clé, impossible de forger les mesures publiées
  à la borne depuis le LAN ; le rolling code jette les rejeux/doublons ;
- **une seule destination** (broadcast OU unicast) : les deux à la fois
  feraient rejeter le doublon avec un warning par seconde.

## 2. Nœud borne (`twc-node.yaml`, Kincony KC868-A6)

### 2.1 Substitutions clés

```yaml
substitutions:
  # DEUX disjoncteurs différents, ne pas confondre :
  twc_breaker_limit_a: "16"    # = limite « Home Load Management » saisie dans Tesla One
  main_breaker_limit_a: "25"   # disjoncteur de branchement (15 kVA tri → 25 A/phase)
  shelly_unavailable_debounce_ms: "10000"  # debounce miroir HA
  recompute_interval: "1000ms"
  udp_fresh_ms: "5000"         # 5 heartbeats manqués avant bascule sur le miroir HA
  contactor_mirror_grace_ms: "30000"
  rs485_tx_pin: GPIO27         # MAX13487E auto-direction : pas de DE/RE
  rs485_rx_pin: GPIO14
  # Entités HA miroir (source de secours) :
  ha_current_a_entity: sensor.<teleinfo>_courant_phase_1
  # … (6 entités mesure + input_boolean.charge_from_grid + contacteur borne)
  ha_contactor_entity: binary_sensor.tesla_wall_connector_contactor_closed
```

### 2.2 ⚠️ LE piège n°1 : jamais de `logger: level: VERBOSE` sur ce nœud

La borne polle en Modbus RTU avec un **timeout de relance ~66 ms**. Les logs
VERBOSE de `modbus`/`modbus_server` (5+ lignes par requête, écrites en
BLOQUANT sur UART0) retardaient la réponse de ~68 ms → la borne avait déjà
renvoyé sa relance → collision (`tx_blocked`), réponse JETÉE, tempête de
relances auto-entretenue : **0 réponse émise depuis le boot** alors que le
flux RX montait. Le niveau DEBUG (défaut) est silencieux par trame → timing
OK. Les logs par paquet UDP sont en V/VV (compilés hors binaire au niveau
DEBUG) → zéro écriture UART par paquet.

Symptôme observable : `TWC Polling Active` OFF + `Poll Interval` absent
pendant que les octets RX défilent.

### 2.3 Émulation Neurio/Generac (modbus_server)

```yaml
uart:
  - id: rs485
    tx_pin: ${rs485_tx_pin}
    rx_pin: ${rs485_rx_pin}
    baud_rate: 115200
    data_bits: 8
    parity: NONE
    stop_bits: 1

modbus:
  - id: wallconn_modbus
    uart_id: rs485
    role: server          # la borne est MAÎTRE et polle

modbus_server:
  - modbus_id: wallconn_modbus
    address: 1
    registers:
      # 1) Bloc d'identité fixe (registres 1-55) : chaîne ASCII du compteur
      #    émulé (« Tesla », firmware « 1.6.1- », modèle VAH4810…) — constantes
      #    reprises du gist public LucaTNT :
      #    https://gist.github.com/LucaTNT/4adf01a7252386559070023612efa117
      # 2) Puissances par CT, FP32 (W) :
      #    0x88=CT1, 0x8A=CT2, 0x8C=CT3, 0x8E=CT4, 0x90=total, 0x92=0
      # 3) Courants par CT, FP32 (A) :
      #    0xF4=CT1 (registre pollé en premier → sert de marqueur de cycle),
      #    0xF6=CT2, 0xF8=CT3, 0xFA=CT4, 0xFC=total
      # 4) Poignée de main d'initialisation « Generac » : 40002-40007
```

Chaque `read_lambda` renvoie une global `ct*_…` recalculée par le script
central `recompute_ct` (jamais de calcul dans la lambda : la réponse doit
partir en < 66 ms). Le registre 0xF4 horodate chaque cycle de poll
(`poll_interval_ms` observé : **~190-200 ms** en régime).

### 2.4 Sémantique RAW + fail-safe (le cœur du firmware)

Depuis le firmware borne 26.18, la borne fait un **contrôle de
plausibilité/corrélation** sur les mesures reçues (quand la voiture charge,
le courant de l'arrivée doit MONTER en corrélation avec sa propre sortie).
L'approche « publier `breaker − disponible` » (PVi1 historique) produit un
plateau figé peu plausible ; ici on publie la **MESURE RÉELLE** de l'arrivée
(courant + puissance par phase, import positif — pas de solaire dans
l'installation de référence, mode GRID) : la borne calcule elle-même
`marge = SA limite (Max Conductor Limit, Tesla One) − mesure publiée`.

Priorité des sources dans `recompute_ct` (tick 1 s + événementiel) :

| Priorité | Source | Condition |
|---|---|---|
| 1 | **UDP direct** | 6 grandeurs vues depuis le boot ET dernier paquet < `udp_fresh_ms` (5 s) — drapeaux `*_seen` : jamais de 0.0 d'init publiés |
| 2 | **miroir HA** | 6 entités disponibles (debounce 10 s) ET `ha_link_ok` (binary_sensor `status` natif **multi-clients** — un drapeau maison basculé par `on_client_disconnected` restait à false quand un client API SECONDAIRE se déconnectait : bug vécu, reported figé) |
| 3 | **fail-safe** | publie conso = `main_breaker` sur les 3 phases → marge 0 → **charge bloquée** (comportement d'un vrai compteur en panne). Au boot, les globals `ct*` sont initialisées à `main_breaker` (sûr par défaut) |

Interrupteur maître `twc_control_enabled` : OFF → publie 0 A partout → marge
maximale → la borne retombe sur son comportement d'usine (le contrôle externe
est neutralisé sans toucher au câblage). Un texte `Linky Source Active`
(UDP/HA/FAILSAFE/OFF/BOOT) trace chaque bascule.

Conséquence assumée de l'UDP : une coupure de HA (reboot) **ne bloque plus la
charge** tant que le flux UDP est frais — le fail-safe n'est PAS affaibli, il
s'arme dès qu'aucune source n'est saine.

### 2.5 Le biais : cible + rampe + application immédiate contacteur ouvert

Levier de régulation universel (fonctionne sur **tout** véhicule branché) :

```
publié = mesure + biais  (A par phase, et biais×230 en W)
⇒ la borne voit « marge = limite − mesure − biais » et bride le véhicule d'autant
```

- `number` **cible** `twc_bias_courant` (0-16 A, pas 0,5, `restore_value:
  false`, initial 0) ;
- global `twc_bias_applied` = biais **réellement appliqué**, publié dans un
  capteur dédié (invisible avant : impossible de diagnostiquer « pourquoi la
  borne refuse de démarrer » pendant une descente de rampe) ;
- script `twc_bias_step(allow_ramp_step)` :
  - **contacteur borne OUVERT** (miroir fiable) → cible appliquée
    **IMMÉDIATEMENT**, dans les deux sens (personne ne charge = pas de
    pilote à protéger). Supprime la fenêtre « code 10 » (160 s de rampe de
    descente pendant lesquelles la borne refusait de démarrer, vécu) ;
  - sinon **rampe** : montée **1 A / 5 s**, descente **0,5 A / 5 s** (tick
    5 s dédié ; les autres appelants — changement de cible, bascule du
    miroir — ne font JAMAIS de pas hors cadence). Raison d'être : un échelon
    de marge pendant la rampe du véhicule = violation du pilote = **trip du
    contacteur** (+58 alertes borne en une journée avant la rampe) ;
  - miroir contacteur jamais vu / indisponible > 30 s / API HA décrochée →
    rampe conservée par prudence (grâce ≤ 30 s : dernier état connu).
- le miroir contacteur est un **`text_sensor` homeassistant, PAS un
  binary_sensor** : la plateforme binaire avale `unavailable`/`unknown` sans
  callback — en text on VOIT l'indisponibilité et on applique la grâce ;
- le biais s'applique en branche NORMALE uniquement — jamais en fail-safe
  (déjà à `main_breaker`) ni quand `twc_control_enabled` est OFF.

### 2.6 Réception UDP (écoute pure)

Côté nœud borne, `packet_transport` est configuré en **providers seulement,
sans ping_pong** → ESPHome ne crée que le socket d'ÉCOUTE (non-bloquant,
drainé dans `loop()`) : ce nœud n'émet RIEN, rien ne peut retarder la réponse
Modbus. Conséquence : le timeout natif du provider (NAN + binary status)
exige ping_pong et est donc INACTIF — la fraîcheur est jugée par notre
horodatage `udp_last_ok_ms` dans `recompute_ct` (même patron que le miroir
HA). Les 6 capteurs `platform: packet_transport` sont internes (zéro entité
HA, zéro recorder).

### 2.7 Observabilité embarquée

Capteurs template (5 s / 2 s) : courants/puissances PUBLIÉS à la borne
(`TWC Reported/Published …`), mesure de la source ACTIVE (`Linky Real …`),
âges (`Linky [UDP] Time Since Last OK`), `TWC Poll Interval` / `Time Since
Last Poll`, `TWC Polling Active`, `Linky UDP Fresh`, `Linky Source Active`,
`TWC biais appliqué`, miroir contacteur diagnostic.

### 2.8 Divers

- OTA = reboot = serveur Modbus coupé → au redémarrage l'ESP publie
  `main_breaker` (marge 0) jusqu'à la première mesure : **ne jamais flasher
  pendant une charge en cours**.
- `compile_process_limit: 1` + UN SEUL builder ESPHome à la fois sur la
  machine (2 builds simultanés = crash vécu).
- Si le nœud borne mutualise d'autres fonctions (cas de Loupiac :
  sécurité eau/forage), le contrôle TWC ne doit toucher QUE l'UART RS485
  libre — aucune broche partagée.

### 2.9 Déclinaisons par carte (cœur commun + paquet de substitutions)

Le cœur (scripts `recompute_ct`/`twc_bias_step`, `modbus_server`, globals,
capteurs d'observabilité) est identique pour toutes les cartes ; seul un
petit paquet de substitutions change : broches UART RS485, éventuel
`flow_control_pin`, réseau (WiFi / LAN8720 / W5500), board PlatformIO.
Structure cible du dépôt : `esphome/twc-node.yaml` (commun) +
`esphome/boards/<carte>.yaml`.

| Carte | Transceiver RS485 | UART TX / RX | Direction | Réseau | Statut |
|---|---|---|---|---|---|
| **Kincony KC868-A6** | MAX13487E | **GPIO27 / GPIO14** | **auto-direction** (aucun DE/RE) | WiFi | ✅ **TESTÉE — référence de production** (poll ~190 ms, chaîne complète validée) |
| **Kincony ESP32-S3 core** (ESP32-S3-WROOM-1U N16R8) | intégré, auto-direction | **GPIO16 / GPIO15** | auto-direction | Ethernet **W5500** (SPI : CLK 43 / MOSI 44 / MISO 42 / CS 41 / INT 2 / RST 1) ; logs via `USB_SERIAL_JTAG` (l'UART0 est réquisitionné par le SPI) ; `board: esp32-s3-devkitc-1` | ⚠️ draft complet existant et **compilé OK** (`twc-control.yaml`), jamais raccordé à une borne |
| **Kincony KC868-A16** | à confirmer (doc Kincony) | **GPIO13 / GPIO16** (source : fiche ESPHome devices + forum HA) | à confirmer | Ethernet LAN8720 | ❌ non testé |
| **Kincony KC868-A4 / A8** | à confirmer | **broches RS485 à confirmer sur la doc Kincony** (non publiées clairement) | à confirmer | WiFi | ❌ non testé |

Règles pour porter le cœur sur une nouvelle carte :
- **Transceiver auto-direction fortement préférable** (MAX13487E ou
  équivalent) : la deadline de réponse Modbus ~66 ms ne laisse aucune marge
  à un basculement DE/RE mal synchronisé. Si la carte exige un pilotage
  DE/RE explicite, déclarer `flow_control_pin` sur le composant `modbus` et
  VALIDER au compteur de polls (`TWC Poll Interval` stable, zéro
  `tx_blocked`) avant toute mise en service.
- Vérifier que l'UART choisie n'entre pas en conflit avec les périphériques
  de la carte (I2C/PCF8574, SPI Ethernet, 1-Wire…) — sur la S3 core, les
  broches UART0 par défaut sont prises par le SPI du W5500.
- Rejouer la QA minimale : polling actif, poll ~200 ms stable, fail-safe
  (couper la source de mesure → publication `main_breaker` → charge
  bloquée en ~10 s), biais 0→16→0 avec et sans charge.
- Mettre à jour le tableau ci-dessus (statut testé/non testé) à chaque
  validation terrain.
