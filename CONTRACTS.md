# Tesla LoadPilot — CONTRATS D'ÉQUIPE (zones disjointes)

> Fichier FIGÉ, propriété de l'architecte. Toute demande de modification des
> interfaces passe par l'orchestrateur. Les trois équipiers travaillent EN
> PARALLÈLE : **personne n'écrit dans la zone d'un autre**. Les interfaces
> ci-dessous (entités, services, clés de config) sont les SEULS points de
> contact — on les lit ici, jamais dans les fichiers du voisin.

## 0. Règles communes (rappel, non négociables)

1. **Aucun secret dans le repo** — `!secret` partout, `esphome/secrets.yaml.example`
   tenu à jour. Ne jamais recopier depuis `/Volumes/config` (lecture seule)
   sans réappliquer l'assainissement : ni clé, ni IP privée cachée en dur,
   ni entity_id Loupiac (`whale_*`, `olimex_portail_*`…).
2. **Rien n'est publié** : pas de `gh`, pas de push, pas de commit — les
   fichiers sont écrits, l'orchestrateur commite.
3. Attribution **PVi1** (github.com/PVi1/esphome-twc-control) + gist LucaTNT
   dans toute doc qui touche l'émulation ; disclaimer non-affiliation Tesla ;
   **aucune image Tesla**.
4. Langues : **anglais** pour README/info.md/code/HACS/dashboards ;
   **français** pour le corpus `docs/` existant et ce fichier.
5. `ARCHITECTURE.md` et `CONTRACTS.md` : lecture seule pour tous.
6. La loi de commande est FIRMWARE et n'a besoin ni de HA ni du cloud
   (ARCHITECTURE.md D2). Personne ne déplace un élément de sécurité vers HA.

## 1. Zones de propriété (fichiers)

### 1.1 Spécialiste HA — possède `custom_components/loadpilot/**` et `esphome/**`

Livrables :

- **Intégration** (`custom_components/loadpilot/`) :
  - `config_flow.py` (+ options flow) sur les clés de `const.py`
    (`charger_node`, `meter_node`, `phases` 1|3, `contract_limit_a`,
    `buffer_pct` défaut 10, `mirror_entities` ×6, `country_profile`) ;
  - coordinator + capteurs dérivés (§3.3), services (§4), `diagnostics.py`,
    `repairs.py` (écart de version firmware/intégration, sources UDP/miroir
    périmées), `translations/en.json` + `fr.json` (libellés fournis par
    l'UX via `dashboards/UX_COPY.md` — il les INTÈGRE, il ne les invente pas) ;
  - `const.py` : il l'étend, il ne RENOMME rien de ce qui y figure.
- **Firmware générique** (`esphome/packages/`) : extraction depuis
  `esphome/kc868-a6-1.yaml` (bloc PVi1-GRADE 17/08) et
  `esphome/olimex-portail.yaml`, selon `esphome/packages/README.md` :
  `twc-core.yaml`, `boards/kc868-a6.yaml` (+ drafts S3), 
  `providers/teleinfo-fr.yaml` (+ squelettes dsmr/sml/ct), `examples/`,
  `secrets.yaml.example`. Il supprime les deux YAML historiques une fois
  l'extraction terminée. Il PRODUIT les entités du §3 exactement.
- Références obligatoires avant d'écrire : `docs/40_LOI_DE_COMMANDE.md`
  (la loi, à transcrire sans « amélioration »), `docs/20_FIRMWARE.md`
  (pièges : VERBOSE interdit sur le nœud borne, deadline 66 ms,
  `rx_buffer_size: 1024`, text_sensor pour le miroir contacteur),
  `docs/15_FOURNISSEURS_MESURE.md` (contrat UDP §1 — INTOUCHABLE).

### 1.2 UX designer — possède `dashboards/**`

Livrables :

- `dashboards/loadpilot-overview.yaml` : vue Lovelace prête à importer
  (état de régulation, publié vs mesuré par phase, marge/headroom, source
  active, biais, escalade, contrôles pause/reprise) — cartes du cœur HA
  uniquement (aucune dépendance HACS tierce obligatoire ; si une variante
  Mushroom est proposée en bonus, TOUJOURS définir explicitement les 4
  actions `tap/hold/double_tap/icon_tap` — piège connu du toggle par défaut) ;
- `dashboards/cards/` : cartes/badges additionnels éventuels ;
- `dashboards/UX_COPY.md` : TOUS les libellés utilisateur (étapes du config
  flow, descriptions des services, textes de notifications types, EN + FR)
  — consommé par le spécialiste HA pour `translations/` ;
- `dashboards/brand/` : visuels ORIGINAUX (SVG) si besoin — zéro asset
  Tesla, zéro capture d'écran Tesla One.

Il consomme UNIQUEMENT les tables §3 et §4 de ce fichier. Si une entité
manque pour son design, il le note dans `dashboards/UX_COPY.md` §Demandes —
il ne l'invente pas dans son YAML.

### 1.3 Rédacteur technique — possède `README.md`, `info.md`, `docs/**`, `CONTRIBUTING.md`, `LICENSE.placeholder`

Livrables :

- `README.md` (anglais) : pitch, non-affiliation Tesla en tête, hardware
  BOM, quick start DOUBLE canal (HACS pour l'intégration + ESPHome remote
  packages pour le firmware, avec `ref:` sur tag), matrice de compatibilité
  (ARCHITECTURE.md D4), attribution PVi1/LucaTNT, avertissement sécurité
  électrique (intervention près du 230 V, disjoncteur coupé) ;
- `info.md` (vitrine HACS, anglais, court) ;
- `docs/` : il réorganise le corpus français existant pour la publication
  (guides d'installation par rôle, page « control law » comme article de
  référence) SANS altérer la substance mesurée de `40_LOI_DE_COMMANDE.md`
  (les valeurs MESURÉ/INFÉRÉ/RAPPORTÉ sont des données, pas du style) ;
- `CONTRIBUTING.md` + politique d'issues (le sujet attire les questions de
  firmware borne : template d'issue avec version TWC obligatoire) ;
- `LICENSE.placeholder` : documente l'intention (MIT pressenti) et le
  BLOCAGE accord PVi1 — pas de LICENSE définitive sans cet accord.

Il ne touche ni au code ni aux YAML ; ses extraits de code sont copiés
depuis les fichiers du spécialiste (à la fin, ou balisés TODO-sync).

### 1.4 Architecte (clos)

`ARCHITECTURE.md`, `CONTRACTS.md`, `hacs.json`,
`custom_components/loadpilot/{manifest.json,const.py,__init__.py}` (état
squelette — le spécialiste HA en prend la suite SAUF renommages),
READMEs de zone (`esphome/packages/`, `esphome/examples/`, `dashboards/`).
`manifest.json` : remplacer `OWNER_TBD` quand le compte de publication est
tranché (question ouverte Vincent).

## 2. Contrat UDP provider → cœur (rappel, figé)

Défini dans `docs/15_FOURNISSEURS_MESURE.md` §1 : port **18511**,
`packet_transport` UDP chiffré XXTEA + rolling code, 6 grandeurs
`lky_ia/ib/ic` (A) + `lky_pa/pb/pc` (VA), import positif, brut (jamais
lissé), heartbeat 1 s + envoi immédiat sur changement, silence en panne.
Monophasé : phases B/C publiées à 0. **Personne ne modifie ce contrat**
(les broadcast_id sont l'ABI du produit).

## 3. Contrat d'entités (produit par le firmware/l'intégration, consommé par dashboards et docs)

Noms de nœuds par défaut : `loadpilot-twc` (borne), `loadpilot-meter`
(compteur). Les entity_id ci-dessous en découlent.

### 3.1 Nœud borne (ESPHome `twc-core.yaml`)

| Entity id | Type | Contenu |
|---|---|---|
| `sensor.loadpilot_twc_published_current_l1/_l2/_l3` | A | courant PUBLIÉ à la borne (symétrique par construction) |
| `sensor.loadpilot_twc_real_current_l1/_l2/_l3` | A | mesure de la source ACTIVE |
| `sensor.loadpilot_twc_real_power_l1/_l2/_l3` | VA | idem puissance |
| `sensor.loadpilot_twc_source_active` | text | `UDP` / `HA` / `FAILSAFE` / `OFF` / `BOOT` |
| `sensor.loadpilot_twc_udp_age` | ms | âge du dernier paquet UDP sain |
| `binary_sensor.loadpilot_twc_udp_fresh` | bool | UDP < 5 s |
| `binary_sensor.loadpilot_twc_polling_active` | bool | la borne polle en Modbus |
| `sensor.loadpilot_twc_poll_interval` | ms | ~190-200 ms attendu |
| `number.loadpilot_twc_bias_target` | A (0-16, pas 0,5) | cible de biais |
| `sensor.loadpilot_twc_bias_applied` | A | biais réellement appliqué (rampe) |
| `number.loadpilot_twc_contract_limit` | A | limite d'abonnement par phase |
| `number.loadpilot_twc_buffer_pct` | % | buffer sécurité (défaut 10) |
| `switch.loadpilot_twc_control_enabled` | bool | kill-switch maître (OFF = borne d'usine) |
| `binary_sensor.loadpilot_twc_escalation_active` | bool | escalade 120 s en cours (publication L+0,1) |
| `sensor.loadpilot_twc_fw_version` | text | version du package (détection d'écart) |

### 3.2 Nœud compteur (providers)

| Entity id | Type | Contenu |
|---|---|---|
| `sensor.loadpilot_meter_current_l1/_l2/_l3` | A | copies throttlées (recorder-friendly) |
| `sensor.loadpilot_meter_power_l1/_l2/_l3` | VA | idem |
| `binary_sensor.loadpilot_meter_overload` | bool | OPTIONNEL — signal compteur générique (FR : STGE bit 7) |

### 3.3 Capteurs dérivés (intégration `loadpilot`)

| Entity id | Contenu |
|---|---|
| `sensor.loadpilot_state` | `regulating` / `idle` / `escalating` / `failsafe` / `off` |
| `sensor.loadpilot_headroom_l1/_l2/_l3` | marge par phase (budget − mesure), A |
| `sensor.loadpilot_worst_phase` | index/nom de la pire phase |

## 4. Contrat de services (domaine `loadpilot`)

| Service | Champs | Sémantique |
|---|---|---|
| `loadpilot.set_bias` | `amps` (0-16, pas 0,5) | écrit la cible de biais (la RAMPE reste firmware) |
| `loadpilot.pause` | — | levier binaire : biais plein (pause de charge propre) |
| `loadpilot.resume` | — | biais 0 (la garde anti-yo-yo/projection est une politique HA ultérieure, pas v0) |

## 5. Ordre de marche et points de synchronisation

- Les trois zones démarrent EN PARALLÈLE, aucune dépendance de fichier.
- Deux rendez-vous d'intégration (orchestrateur) : (1) UX_COPY.md →
  translations/ ; (2) extraits de code → README/docs. Jusque-là, chacun
  code contre les tables de CE fichier.
- Toute incohérence découverte entre une table §3/§4 et la réalité du code
  se signale à l'orchestrateur — on corrige LE CONTRAT ou LE CODE, jamais
  silencieusement l'un des deux.
