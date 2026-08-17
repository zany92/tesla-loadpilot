# Tesla LoadPilot — fournisseurs de mesure enfichables (module 2)

> Le cœur (nœud borne, `20_FIRMWARE.md` §2) ne connaît QUE six grandeurs :
> courant et puissance apparente par phase. Il se moque totalement de qui les
> mesure et dans quel pays. Tout appareil capable de les diffuser selon le
> contrat UDP ci-dessous est un « provider » valable — la téléinfo Linky
> française n'est que le premier exemple, celui qui tourne en production.

## 1. Le contrat UDP (interface provider → cœur)

| Élément | Valeur | Pourquoi |
|---|---|---|
| Transport | ESPHome `udp` + `packet_transport` (platform udp), port **18511** | Composants OFFICIELS (rien d'écrasable par une MàJ), socket non-bloquant côté récepteur |
| Grandeurs | 6 capteurs : `lky_ia/ib/ic` (courant par phase, A) + `lky_pa/pb/pc` (puissance apparente par phase, VA) | Ce que le cœur publie à la borne (registres courant ET puissance). Monophasé : publier les phases B/C à 0 |
| Cadence | `update_interval: 1s` = re-diffusion COMPLÈTE (heartbeat) ; les changements de valeur partent EN PLUS immédiatement (paquet incrémental, boucle suivante) | La fraîcheur côté cœur est jugée sur le dernier paquet reçu (`udp_fresh_ms` 5 s = 5 heartbeats manqués avant bascule sur le miroir HA) |
| Chiffrement | `encryption:` (XXTEA, clé hachée SHA-256) **identique des deux côtés** + `rolling_code_enable: true` (anti-rejeu, persisté en flash, usure nulle) | Sans la clé, impossible de forger les mesures publiées à la borne depuis le LAN |
| Adressage | broadcast 255.255.255.255 par défaut ; **unicast** vers l'IP du cœur si le réseau bloque le broadcast LAN→WLAN. **Une seule destination à la fois** (le rolling code rejette les doublons) | |
| Taille | `broadcast_id` courts → paquet ~120 octets, ≤ 2 paquets/s | Aucun risque pour la deadline Modbus 66 ms du cœur (mesuré) |
| Sémantique | Import positif, valeurs RÉELLES de l'arrivée (voiture incluse). Pas de lissage côté provider : le cœur et la borne veulent du brut | La borne 26.18 vérifie la CORRÉLATION entre sa sortie et la mesure — une mesure lissée ou partielle casse la plausibilité |

Exigences qualité :
- **latence** : viser ≤ 1,5 s capteur → paquet (voir `40_LOI_DE_COMMANDE.md`
  §5 : à 3 s la borne rebondit, à 15 s elle pompe en bang-bang) ;
- **pas de zéros d'init** : ne diffuser une grandeur qu'une fois réellement
  mesurée (le cœur s'en protège aussi par ses drapeaux `*_seen`) ;
- en panne de capteur : **se taire** (le heartbeat cesse, le cœur bascule
  sur le miroir HA puis le fail-safe) — ne JAMAIS diffuser une dernière
  valeur figée.

Squelette minimal d'un provider :

```yaml
udp:
  id: udp_meter
#  addresses: ["<IP_NOEUD_BORNE>"]     # unicast si broadcast bloqué

packet_transport:
  - platform: udp
    udp_id: udp_meter
    update_interval: 1s
    encryption: !secret udp_meter_key   # = clé du cœur
    rolling_code_enable: true
    sensors:
      - { id: meter_i1, broadcast_id: lky_ia }
      - { id: meter_i2, broadcast_id: lky_ib }
      - { id: meter_i3, broadcast_id: lky_ic }
      - { id: meter_p1, broadcast_id: lky_pa }
      - { id: meter_p2, broadcast_id: lky_pb }
      - { id: meter_p3, broadcast_id: lky_pc }
```

(Le nom de provider déclaré côté cœur — `providers: [name: …]` — doit être
le `name:` ESPHome du nœud émetteur.)

## 2. Critère d'éligibilité : la CADENCE avant tout

**Un provider est éligible s'il fournit les courants PAR PHASE à ~1 Hz.
En dessous, le bang-bang de la borne est GARANTI ; au-delà, AUCUN gain**
(verdict final 14/08 : à 0,46 s la borne ne tient toujours pas de palier
sous la consigne — le plafond est dans le firmware TWC, pas la mesure,
cf. `40_LOI_DE_COMMANDE.md`) — preuve mesurée
dans `40_LOI_DE_COMMANDE.md` §5 : à 15 s de cadence effective le DPM pompe
(cycles 16→0→16 A), à 3 s il rebondit encore à chaque rampe du véhicule,
à 1,1 s les descentes deviennent propres. La borne soustrait son courant
INSTANTANÉ d'une mesure réseau datée : chaque seconde de latence se paie en
erreur transitoire pendant les rampes (~1 A/s côté véhicule).

| Source | Pays | Cadence des courants | Éligibilité |
|---|---|---|---|
| TIC Linky mode **standard** | FR | ~1 s (refresh interne Linky ~1 Hz, plafond Enedis) | ✅ **prouvé en production** |
| TIC Linky mode **historique** | FR | ~1,5-2 s, et ampères ENTIERS (IINST) | ⚠️ dégradé (quantification ±0,5 A, pas de SINSTS par phase) |
| **DSMR 5** port P1 | NL/BE | 1 s (télégramme chaque seconde) | ✅ |
| **DSMR 4** port P1 | NL (anciens) | 10 s | ❌ bang-bang garanti |
| **Smarty** P1 | LU | port physique DSMR5 mais **publication ~10 s** (intervalle DSMR4) + télégrammes CHIFFRÉS (clé personnelle à demander à Luxmetering) — sources : issue dsmr-reader #769, intégration `dsmr` HA (variante « Luxembourg V5 ») | ❌ (à re-vérifier sur compteur récent) |
| **SML** tête IR (D0) | DE/AT | ~1-4 s selon le compteur (ISKRA MT681, EMH eHZ… ; sources : doc Tasmota Smart Meter Interface, stromleser.de) ; ⚠️ **PIN** souvent requis pour débloquer la puissance instantanée ; souvent puissance TOTALE seule | ✅/⚠️ selon modèle — vérifier cadence ET grandeurs par phase |
| **UK SMETS 1/2** | UK | pas de port local consommateur (HAN Zigbee réservé aux CAD certifiés) | ❌ → pinces CT |
| **Shelly Pro 3EM** (pinces) | tous | ~1 s en push local (WebSocket/UDP RPC) | ✅ |
| **ATM90E32 / CircuitSetup**, PZEM | tous | sub-seconde (lecture SPI/UART directe par l'ESP) | ✅✅ (aussi la voie « étage sub-seconde ») |

**Recommandation de repli : quand le compteur national ne suit pas (DSMR 4,
Smarty, SMETS, SML total-seul), poser des pinces CT** (Shelly Pro 3EM
~120 €, ou ATM90E32 pour l'intégration la plus directe) sur l'arrivée — le
contrat UDP est le même, et on gagne au passage la meilleure latence de
toute la famille.

## 3. Providers par pays / technologie

| Provider | Pays / cas | Composant ESPHome | Matériel | Statut |
|---|---|---|---|---|
| **Téléinfo TIC standard** | France (Linky) | `teleinfo` | Hat Hallard « WeMos TeleInfo » (https://www.tindie.com/products/hallard/wemos-teleinfo/), RX seul, 9600 bd 7E1 | **EN PRODUCTION** (référence, `20_FIRMWARE.md` §1). Tri : IRMS1-3 + SINSTS1-3 natifs |
| **Port P1 / DSMR** | Pays-Bas, Belgique, Luxembourg (et Scandinavie via variantes) | `dsmr` | Câble P1 (RJ12) + inversion éventuelle, l'ESP se branche directement | Squelette à écrire. DSMR expose courant et puissance PAR PHASE en standard |
| **Tête IR SML** | Allemagne, Autriche (compteurs eHZ/MME) | `sml` | Tête de lecture IR (photodiode) collée au compteur | Squelette à écrire. ⚠️ beaucoup de compteurs SML ne donnent que la puissance TOTALE signée — reconstruire les phases exige des pinces, ou publier total/3 (dégradé, à documenter honnêtement) |
| **Pinces CT universelles** | Tout pays, tout compteur | capteur natif HA (Shelly Pro 3EM en local push) OU `pzemac`/PZEM-004T v3, OU `atm90e32` (6 canaux) | Shelly Pro 3EM (~120 €), PZEM-004T (~15 €/phase), carte ATM90E32 | Squelette à écrire. C'est AUSSI la voie « étage sub-seconde » : des pinces dédiées lues par l'ESP passent sous la seconde, là où un compteur fiscal plafonne (Linky ~1 Hz) |

Notes de généralisation :
- **Monophasé** (TWC Gen 3 mono, majorité des pays) : un seul courant/une
  seule puissance à mesurer, publier B/C à 0 — le cœur et la borne
  fonctionnent tels quels (la borne raisonne alors sur sa seule phase).
- Le **miroir HA** du cœur (source 2) est indépendant du provider UDP : tout
  capteur HA courant/puissance par phase peut le nourrir via les
  substitutions `ha_*_entity` — un provider UDP sans miroir HA est valide
  (le fail-safe prend le relais en cas de panne), mais on perd l'étage de
  secours.
- Les particularités françaises restent confinées au provider : Tempo/HP-HC,
  registre STGE (bit 7 « dépassement en cours » = signal d'escalade de la
  couche HA), `rx_buffer_size: 1024` pour les trames Tempo longues.

## 4. Recette : écrire un nouveau provider

1. **Choisir la source** : composant ESPHome existant (`teleinfo`, `dsmr`,
   `sml`, `pzemac`, `atm90e32`…) ou capteurs poussés par HA.
2. **Obtenir les 6 grandeurs** courant/puissance apparente par phase, en
   unités A et VA, import positif, sans lissage. Donner un `id:` à chaque
   capteur (le `name:` HA est facultatif — un capteur `internal: true`
   diffuse très bien).
3. **Découpler recorder et diffusion** si le capteur est bavard : capteur de
   base `internal` sans throttle (lu par `packet_transport`) + `platform:
   copy` throttlée portant le `name:` (entité HA) — patron du provider
   téléinfo (`20_FIRMWARE.md` §1.3).
4. **Coller le bloc UDP** du §1 avec les `broadcast_id` EXACTS
   (`lky_ia`…`lky_pc`) et la clé partagée.
5. **Vérifier la latence** : viser ≤ 1,5 s. Mesurer côté cœur avec
   `Linky UDP Time Since Last OK` (attendu < ~1 100 ms en régime).
6. **Tester les pannes** : couper la source → le heartbeat doit cesser →
   côté cœur `Linky Source Active` passe UDP → HA → FAILSAFE (charge
   bloquée). C'est le comportement attendu, pas un bug.
7. **Documenter** la cadence native du compteur (le Linky plafonne à ~1 Hz,
   un DSMR 5 à 1 Hz, un SML souvent moins) : c'est elle qui borne la
   réactivité de toute la chaîne.
