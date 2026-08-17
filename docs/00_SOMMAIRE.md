# Tesla LoadPilot — dossier technique
## Contrôle dynamique Tesla Wall Connector Gen 3 par émulation Neurio

> **Staging documentaire (14/08/2026)** en préparation d'une future publication
> GitHub. **RIEN n'est publié.** Ce dossier est une réécriture GÉNÉRICISÉE et
> SANS SECRET des configs et docs vivants de Loupiac — les fichiers de
> production restent la seule source de vérité opérationnelle
> (`/config/esphome/*.yaml`, `/config/packages/*.yaml`,
> `/config/docs/contrat_electrique_LOGIQUE.md`).

## Le projet en une phrase

> **Any meter, any country, any vehicle — no discontinued Neurio required.**

Piloter dynamiquement la puissance de charge d'un **Tesla Wall Connector
Gen 3** (fonction *Home Load Management* / DPM, firmware ≥ 26.18) sans le
compteur Neurio abandonné : un ESP32 émule le compteur Neurio/Generac en
esclave Modbus RTU sur le bus RS485 interne de la borne et lui publie les
mesures réelles de l'arrivée, enrichies d'un **biais de courant** pilotable
qui devient le seul levier matériel valable sur **n'importe quel véhicule**
branché (invité compris).

### Note de nommage

Nom retenu : **« Tesla LoadPilot »** (dépôt probable `tesla-loadpilot`).
L'usage de la marque Tesla dans les noms de projets open source est une
pratique répandue et tolérée (TeslaMate, TeslaFi, TWCManager…), mais le
README portera en tête le disclaimer standard : *« This project is not
affiliated with, endorsed by, or sponsored by Tesla, Inc. »* — et aucun
logo/visuel Tesla ne sera utilisé.

## Architecture de publication : DEUX MODULES (décision Vincent, 14/08)

1. **Le cœur universel** (nœud borne) : émulation Neurio, sémantique RAW,
   biais/rampe, fail-safe, priorité de sources, loi de commande mesurée.
   **Rien de spécifique à la France** — valable pour toute borne TWC Gen 3,
   mono ou triphasée, quel que soit le compteur en amont. Le cœur est
   lui-même **multi-cartes** : logique commune + paquet de substitutions
   par carte Kincony (`20_FIRMWARE.md` §2.9 — seule la KC868-A6 est
   validée à ce jour).
2. **Des « fournisseurs de mesure » enfichables** via la liaison UDP
   (contrat de diffusion documenté). Notre téléinfo Linky (hat Hallard)
   n'est que le PREMIER exemple : port P1 (NL/BE/LU), tête IR SML (DE/AT),
   pinces CT universelles… → voir `15_FOURNISSEURS_MESURE.md`.

## Contenu du dossier

| Fichier | Contenu |
|---|---|
| `00_SOMMAIRE.md` | Ce plan + décisions actées + questions ouvertes |
| `10_MATERIEL.md` | BOM de l'installation de référence, câblage, schéma d'architecture |
| `15_FOURNISSEURS_MESURE.md` | Module 2 : providers par pays + recette d'un nouveau provider (contrat UDP) |
| `20_FIRMWARE.md` | Les deux configs ESPHome expliquées et généricisées + déclinaisons par carte |
| `30_COMMISSIONING_TESLA_ONE.md` | Le pas-à-pas Tesla One vécu (déclaration du compteur, CT, limites) |
| `40_LOI_DE_COMMANDE.md` | **La valeur du projet** : le comportement MESURÉ du DPM firmware 26.18 |
| `50_COUCHE_HA.md` | Vue d'ensemble du package Home Assistant (voiture-d'abord, levier binaire…) |
| `90_SECRETS_A_REGENERER.md` | Checklist des secrets à régénérer AVANT toute publication |

## Plan proposé pour le futur dépôt

```
tesla-loadpilot/
├── README.md                      ← pitch, BOM, schéma, quick start
│                                     + disclaimer « not affiliated with Tesla, Inc. »
├── LICENSE                        ← à choisir (question ouverte)
├── docs/
│   ├── hardware.md                ← 10_MATERIEL
│   ├── providers.md               ← 15_FOURNISSEURS_MESURE
│   ├── commissioning.md           ← 30_COMMISSIONING_TESLA_ONE
│   ├── control-law.md             ← 40_LOI_DE_COMMANDE (l'article « recherche »)
│   └── ha-integration.md          ← 50_COUCHE_HA
├── esphome/
│   ├── twc-node.yaml              ← LE CŒUR (module 1, logique commune)
│   ├── boards/                    ← paquets de substitutions par carte
│   │   ├── kc868-a6.yaml          ←   référence TESTÉE (GPIO27/14, MAX13487E)
│   │   ├── esp32-s3-core.yaml     ←   draft existant (GPIO16/15, Ethernet W5500)
│   │   └── kc868-a4|a8|a16.yaml   ←   déclinaisons à valider (20_FIRMWARE §2.9)
│   ├── providers/
│   │   ├── teleinfo-fr.yaml       ← olimex ESP32-POE généricisé (module 2, exemple 1)
│   │   ├── dsmr-p1.yaml.example   ← squelettes à écrire (cf 15_…)
│   │   └── sml-de.yaml.example
│   └── secrets.yaml.example
└── homeassistant/                 ← si le périmètre l'inclut (question ouverte)
    └── packages/…
```

## Décisions ACTÉES (Vincent, 14/08/2026)

- **Nom : « Tesla LoadPilot »** (dépôt probable `tesla-loadpilot`) — voir la
  note de nommage ci-dessus (disclaimer non-affiliation obligatoire).
- **Module indépendant** — PAS une contribution/PR au dépôt
  PVi1/esphome-twc-control. Attribution claire à PVi1 comme source
  d'inspiration/base initiale. **Vérifié le 14/08 sur GitHub : le dépôt
  PVi1/esphome-twc-control n'affiche AUCUNE licence explicite** (ni fichier
  LICENSE ni mention sidebar) → par défaut « tous droits réservés » :
  **demander l'accord de l'auteur** pour les portions dérivées avant
  publication. Distinction à faire dans l'attribution :
  - *dérivé/inspiré* : l'idée d'émuler le Neurio en ESPHome, la structure
    des registres Modbus (adresses 0x88-0x92 / 0xF4-0xFC, poignée de main
    Generac) ; le bloc d'identification lui-même vient d'un gist public de
    LucaTNT (à créditer aussi :
    https://gist.github.com/LucaTNT/4adf01a7252386559070023612efa117) ;
  - *original (majoritaire)* : sémantique RAW (publier la vraie mesure, pas
    `breaker − avail`), biais/rampe/application immédiate, liaison UDP
    multi-sources avec priorité et fail-safe, contrainte des 66 ms
    documentée, toute la loi de commande mesurée (40_), la couche HA (50_).
- **Structure deux modules** cœur universel + providers enfichables
  (ci-dessus).
- **Nœud téléinfo de référence = Olimex ESP32-POE** (confirmé Vincent,
  fiche : https://www.olimex.com/Products/IoT/ESP32/ESP32-POE/open-source-hardware)
  — réconciliation de la config Ethernet dans `10_MATERIEL.md` /
  `20_FIRMWARE.md` §1.2.
- **Cœur multi-cartes Kincony** : structure commune + substitutions par
  carte, tableau GPIO/transceiver et statut testé/non testé dans
  `20_FIRMWARE.md` §2.9.
- **Illustrations : AUCUNE image sous copyright tiers dans le dépôt.** Les
  visuels Tesla ne sont jamais reproduits : on LIE la doc officielle
  d'installation du Wall Connector (URL) et tous les schémas (RS485,
  architecture) sont des originaux mermaid/ASCII du projet
  (`10_MATERIEL.md` §2). Photos personnelles de l'installation bienvenues
  plus tard.

## Questions ouvertes pour Vincent

1. **Licence du dépôt.** MIT (écosystème ESPHome) ? GPLv3 ? À articuler avec
   l'accord à obtenir de PVi1 (pas de licence explicite chez lui) et le
   crédit LucaTNT.
2. **Périmètre : firmware seul, ou firmware + package HA ?** Le firmware est
   généralisable presque tel quel ; le package HA (6 200 lignes) est
   fortement couplé à Loupiac (délestage, phases, Sonos, Fleet). Option
   médiane : firmware + mini-package HA d'exemple (biais, mode manuel,
   garde anti-yo-yo) et la logique complète en doc.
3. **Compte de publication** (zany92 ?) et politique d'issues (le sujet
   attire les questions de firmware borne).

## Trous documentaires restants (état 14/08/2026)

- ~~Test « palier »~~ **FAIT (14/08 15:11, verdict final)** : même à 0,46 s
  la borne ne tient pas un palier sous la consigne — plafond du firmware
  TWC, pas la latence. Conclusion intégrée à `40_LOI_DE_COMMANDE.md`.
- **Protocole T1-T6** (critères chiffrés, PLAN_lot13) à rejouer avec
  `borne_seul` OFF pour valider le pilotage Fleet + biais en réel.
- **Valeur exacte « Home Load Management »** dans Tesla One à reporter dans
  `twc_breaker_limit_a` (16 A provisoire) ; `main_breaker_limit_a` = 25 A à
  confirmer sur le disjoncteur de branchement.
- **Déclinaisons de cartes Kincony** (`20_FIRMWARE.md` §2.9) : seule la
  KC868-A6 est validée ; broches RS485 A4/A8 à confirmer sur la doc
  Kincony ; ESP32-S3 core = draft compilé jamais branché à une borne.
- **Providers non-français** (`15_FOURNISSEURS_MESURE.md`) : squelettes dsmr
  / sml / pinces CT à écrire et à faire valider par des testeurs des pays
  concernés — aucun n'a tourné en réel.
- Le **refresh interne du Linky (~1 Hz)** et le plafond TIC 9600 bd sont des
  limites Enedis non configurables : à sourcer proprement
  (Enedis-NOI-CPT_54E) pour la publication.
- **Accord de PVi1** à demander (portions dérivées, cf. décisions actées).
