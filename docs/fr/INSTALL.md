# Guide d'installation - France (Linky, téléinfo TIC)

> Parcours complet pour l'installation de référence : Linky en mode TIC
> standard, nœud compteur Olimex ESP32-POE + hat Hallard, nœud borne
> Kincony KC868-A6, Tesla Wall Connector Gen 3 (firmware ≥ 26.18).
>
> **État du projet : bêta privée.** Les paquets ESPHome génériques
> (`esphome/packages/`) et l'intégration HACS sont en cours d'extraction
> depuis le firmware de référence - les étapes qui en dépendent sont
> décrites au futur et balisées `TODO-sync`. Les étapes matérielles,
> le commissioning Tesla One et les pièges sont, eux, vécus et validés
> en production.
>
> *Projet indépendant, non affilié à Tesla, Inc.*

## ⚠️ 0. Sécurité électrique - à lire en entier avant d'ouvrir quoi que ce soit

- Le bornier RS485 du Wall Connector est **derrière la façade, à quelques
  centimètres de parties sous 230 V**. **Coupez le disjoncteur dédié de la
  borne** avant de déposer la façade, et vérifiez l'absence de tension.
- Le raccordement TIC se fait sur les bornes I1/I2 du Linky : elles sont en
  très basse tension de sécurité, mais elles sont **dans ou à côté du
  tableau / panneau de comptage**. Coupez ce qui doit l'être, ne travaillez
  jamais seul·e dans un tableau sous tension.
- Si vous n'êtes pas à l'aise avec une intervention en tableau électrique,
  **faites réaliser le câblage par un électricien qualifié**.
- Vous utilisez ce projet **sous votre propre responsabilité**. Une
  mauvaise configuration peut neutraliser complètement la gestion de charge
  (vécu : limites Tesla One mal posées = aucun bridage, voir §4) - testez
  toujours en mode ombre avant d'activer (§6).
- Règle absolue de flash : **jamais d'OTA pendant une charge en cours**
  (reboot = serveur Modbus coupé = publication fail-safe au redémarrage).

## 1. Prérequis

### Matériel (BOM détaillée : [`10_MATERIEL.md`](10_MATERIEL.md))

| Rôle | Matériel |
|---|---|
| Compteur | Linky (mono ou tri) passé en **TIC mode standard** (demande via votre fournisseur/Enedis si encore en historique - le mode historique est dégradé : ampères entiers, pas de puissance par phase) |
| Nœud compteur | Olimex ESP32-POE + hat Hallard « WeMos TeleInfo » (RX GPIO36) |
| Nœud borne | Kincony KC868-A6 (référence validée ; autres cartes : [`20_FIRMWARE.md`](20_FIRMWARE.md) §2.9) |
| Borne | Tesla Wall Connector Gen 3, firmware ≥ 26.18 |
| Liaison | CAT5e (une paire torsadée + masse), longueur courte de préférence |

### Logiciel

| Composant | Minimum |
|---|---|
| Home Assistant | 2025.12 |
| ESPHome | 2025.2 (`packet_transport` chiffré + rolling code) |
| Application Tesla One | version courante (accès local, compte pro non requis) |

### Secrets - AVANT tout flash

Copiez `esphome/secrets.yaml.example` vers votre `secrets.yaml` ESPHome et
renseignez toutes les valeurs (WiFi, clés API ESPHome, mots de passe OTA,
**clé UDP partagée** entre les deux nœuds - c'est elle qui chiffre les
mesures en XXTEA). Le fichier `secrets.yaml` **ne se commite jamais**
(voir [`../SECURITY.md`](../../SECURITY.md)).

## 2. Nœud compteur (Olimex ESP32-POE + hat Hallard)

1. **Câblage TIC** : deux fils entre les bornes **I1/I2** du Linky et
   l'entrée TIC du hat Hallard (opto-isolée, pas de polarité critique sur
   ce hat). Le hat se monte sur le port UART de l'Olimex - **RX GPIO36**,
   9600 bd, 7E1, mode standard.
2. **Réseau** : l'ESP32-POE s'alimente et se connecte en Ethernet (PoE ou
   USB). La config déclare `power_pin: GPIO12` (alimentation du PHY
   LAN8720) - sans lui, l'Ethernet peut ne pas revenir après un soft-reset
   sur certains exemplaires ([`20_FIRMWARE.md`](20_FIRMWARE.md) §1.2).
3. **Flash** : compilez et flashez le YAML du nœud compteur depuis le
   dashboard ESPHome (premier flash par USB, ensuite OTA).
   `TODO-sync` : le fichier à utiliser sera
   `esphome/packages/providers/teleinfo-fr.yaml` consommé via un
   entrypoint d'exemple (`esphome/examples/`), épinglé sur le tag de
   release (`ref: vX.Y.Z`) - en attendant l'extraction, le fichier de
   référence assaini est `esphome/olimex-portail.yaml`.
4. **Vérifications** :
   - les 6 grandeurs (IRMS1-3, SINSTS1-3) remontent dans HA et varient ;
   - piège n°1 : **`rx_buffer_size: 1024` obligatoire** (une trame Tempo
     standard dépasse 400 octets ; à 256, 2 trames sur 3 se perdent et la
     cadence effective tombe à ~15 s → la borne pompera) ;
   - en Tempo, vérifiez que la cadence reste ~1 Hz.

En monophasé : seules IRMS1/SINSTS1 existent - les phases B/C sont
publiées à 0, le reste de la chaîne fonctionne tel quel.

## 3. Nœud borne (Kincony KC868-A6)

1. **DISJONCTEUR DE LA BORNE COUPÉ.** Déposez la façade du Wall Connector.
2. **Câblage RS485** (schéma complet : [`10_MATERIEL.md`](10_MATERIEL.md) §2) :
   - borne **A** du KC868-A6 → fil **rouge** (A+) du bornier RS485 interne ;
   - borne **B** → fil **blanc** (B−) ;
   - **masse commune** entre les deux ;
   - pas de terminaison 120 Ω nécessaire sur liaison courte (validé en
     production) ; en prévoir si la liaison dépasse quelques mètres ou si
     des erreurs de trame apparaissent ;
   - pour référence, la spécification **officielle** Tesla (app note DPM)
     pour le compteur : paire torsadée **blindée**, longueur **120 m
     max**, drain du blindage **à la terre côté tableau** (une seule
     extrémité). Sur liaison longue ou en environnement bruité,
     alignez-vous dessus. À noter : des montages communautaires
     fonctionnent sans masse commune ni terminaison (gist LucaTNT) - notre
     référence utilise la masse commune, les deux existent sur le terrain.
3. **Flash** du firmware nœud borne (mêmes remarques : premier flash USB,
   `secrets.yaml` renseigné). `TODO-sync` : cible =
   `esphome/packages/twc-core.yaml` + `esphome/packages/boards/kc868-a6.yaml`
   épinglés sur tag ; en attendant, référence assainie =
   `esphome/kc868-a6-1.yaml` (bloc « PVi1-GRADE 17/08 »).
4. **Substitutions à ajuster à VOTRE installation** :
   - limite de contrat par phase (ex. 15 kVA tri : 5 000 VA / 230 V ≈ 21 A) ;
   - disjoncteur de branchement (`main_breaker`) - c'est la valeur publiée
     en fail-safe pour bloquer la charge ;
   - buffer de sécurité (défaut 10 %).
5. **Refermez la façade, réarmez la borne.**
6. **Vérifications** :
   - `TWC Polling Active` = on et `TWC Poll Interval` stable ~190-200 ms :
     la borne polle le compteur émulé ;
   - des octets RX mais **zéro trame valide** → polarité : **permutez A et
     B** (piège vécu et confirmé côté communauté : « A → +, B → −, et
     inverser si muet ») ;
   - si la borne ne polle toujours pas : **redémarrez l'ESP32 APRÈS que la
     borne est en ligne** (retour communautaire validé - l'ordre de
     démarrage compte pour que la borne détecte le compteur) ;
   - **vitesse du bus** : les sources communautaires rapportent tantôt
     **9600**, tantôt **115200 bauds** selon les installations et versions.
     Notre firmware de référence fonctionne tel que fourni - n'y touchez
     pas ; si vous portez la config sur une autre base et que le bus reste
     muet à polarité correcte, essayez les deux vitesses ;
   - piège n°1 du nœud borne : **jamais `logger: level: VERBOSE`** - les
     logs bloquants font rater la deadline de réponse Modbus (~66 ms) et
     la borne n'obtient plus une seule réponse ([`20_FIRMWARE.md`](20_FIRMWARE.md) §2.2) ;
   - `Source Active` = UDP et `UDP Fresh` = on (si le réseau
     bloque le broadcast LAN→WLAN, passez l'UDP en unicast vers l'IP du
     nœud borne - une seule destination à la fois).

## 4. Commissioning Tesla One - sans lui, RIEN ne bride

Pas-à-pas complet et pièges vécus :
[`30_COMMISSIONING_TESLA_ONE.md`](30_COMMISSIONING_TESLA_ONE.md). Résumé :

1. Connectez-vous au hotspot de commissioning de la borne (QR sous la
   façade), menu installateur → *Home Load Management* → ajouter un
   compteur : la borne détecte le **Neurio** émulé.
2. **CT 1/2/3 = Conductor** (phases L1/L2/L3), CT 4 = None. En monophasé :
   CT 1 seul.
3. **L'ordre des limites compte** : le champ *Max Conductor Limit* refuse
   toute valeur inférieure au *Max Output Current* de la borne → **baissez
   d'abord Max Output Current** (ex. 16 A), puis posez le Conductor Limit
   de votre contrat (21 A pour 15 kVA tri).
4. Reportez ces valeurs dans les substitutions du firmware (limite Home
   Load Management et disjoncteur de branchement).
5. **Vérifiez que le DPM agit** : lancez une charge, créez un dépassement
   contrôlé (bouilloire, four…), observez les vitals locaux
   (`http://<IP_BORNE>/api/1/vitals`) : réaction attendue ≤ 5 s.
   - Ne jugez **jamais** la charge sur l'API cloud du véhicule (poll
     ~10 min, se fige) - vitals locaux ou intégration
     `tesla_wall_connector` uniquement.
   - Conductor Limit resté à 32 A sur un contrat 21 A = « jamais de
     bridage » : c'est LE piège qui a fait conclure deux fois à tort
     « le DPM ne marche pas ».

### Verrou installateur (firmware ≥ 26.2.0) et contournement

Depuis le firmware **26.2.0** environ, plusieurs installations rapportent
que la déclaration du compteur externe est **verrouillée derrière des
identifiants installateur Tesla One** (sans activation, la borne n'initie
jamais le polling Modbus). Contournement **validé par la communauté sur
26.18** (notre version) : un **compte Tesla générique** suffit - dans
l'app Tesla, **More → « Tesla device settings »** donne accès à la
configuration de l'appareil sans compte pro. Notre commissioning de
référence (hotspot + Tesla One, §ci-dessus) a fonctionné sans compte pro
sur 26.18 ; si le menu vous est refusé, passez par ce contournement.
Gardez en tête que cette porte n'a rien d'officiel : Tesla peut la
refermer à toute mise à jour.

### Recommandation FORTE : gelez le firmware de la borne

Toute la chaîne (verrou d'activation contourné, constantes de
comportement mesurées sur 26.18, couche de plausibilité) repose sur un
firmware borne **non documenté et mouvant** - la communauté a déjà vécu
un changement de comportement attribué à une MAJ, et un downgrade est
impossible. **Si votre installation le permet, bloquez les mises à jour
automatiques de la borne** (pas de méthode officielle documentée -
question communautaire ouverte). A minima, notez la version firmware
avant/après toute MAJ et re-déroulez la validation
([`BEHAVIOR.md`](BEHAVIOR.md) §8) après chaque changement.

> ⚠️ **Invariant d'exploitation - ne publiez JAMAIS une valeur inférieure
> au courant propre de la borne.** Un vrai compteur en tête d'installation
> ne peut physiquement pas mesurer moins que ce que la borne tire
> elle-même : le firmware le détecte et entre dans un **état de défiance**
> où le compteur émulé est durablement ignoré (service, protection et
> escalade compris) - voir [`BEHAVIOR.md`](BEHAVIOR.md) §4. Le bloc de
> publication de référence respecte cet invariant par construction (la
> mesure publiée inclut la branche de la borne) ; toute modification
> locale doit le préserver, y compris pendant les rampes du véhicule.

## 5. Intégration Home Assistant (HACS)

`TODO-sync` - l'intégration est en cours de développement ; le parcours
cible sera :

1. HACS → dépôts personnalisés → ajouter ce dépôt (catégorie
   *Intégration*) → installer **Tesla LoadPilot** → redémarrer HA.
2. Paramètres → Appareils et services → Ajouter l'intégration
   « Tesla LoadPilot » : le config flow demandera les nœuds ESPHome
   (borne, compteur), le nombre de phases (1|3), la limite de contrat, le
   buffer, et les entités miroir (6 capteurs courant/puissance - la source
   de SECOURS quand l'UDP se tait).
3. L'intégration écrira les réglages **résidents sur le nœud borne**
   (limite, buffer, biais, kill-switch) : un reboot de HA ne change rien à
   la borne, et la régulation vit sans HA.

L'intégration signalera par une *Réparation* HA tout écart de version
firmware/intégration (les deux canaux s'installent sur le **même tag**).

## 6. Premiers tests - TOUJOURS en ombre d'abord

Le firmware expose un sélecteur de mode de signal (`Signal Mode`, trois
positions : `RAW`, `OMBRE-MAX`, `ACTIF-MAX`). **Attention : tel que
livré, le nœud démarre en `ACTIF-MAX`** (voir la note en fin de section) -
votre **premier geste après le flash** est donc de passer le sélecteur en
`RAW`, puis de gravir l'échelle ci-dessous. **Ne restez jamais en actif
sans avoir observé l'ombre d'abord** :

1. **Dry-run : mode `OMBRE-MAX`.** La borne continue de voir la mesure
   brute (RAW) ; le capteur « Shadow Published Current » montre ce que le
   bloc pire-phase-symétrique-clampé PUBLIERAIT (une seule valeur : la
   publication est symétrique sur les trois phases par construction).
   Pendant une charge réelle, vérifiez sur plusieurs dizaines de minutes :
   - shadow ≤ limite en permanence (clamp) ;
   - aucune valeur aberrante (NaN, 0 transitoire au boot).
2. **Activation : mode `ACTIF-MAX`**, de préférence charge en cours et
   maison chargée (le scénario nominal). Attendu (validation de référence,
   [`BEHAVIOR.md`](BEHAVIOR.md) §8) : modulation douce sous la consigne,
   paliers tenus, remontée ~1 A / 30 s, **zéro ouverture de contacteur**
   (notez le compteur de cycles lifetime avant/après).
3. **Abandon immédiat si** : la borne ignore le signal > 2 min, TOUTE
   ouverture de contacteur, polling interrompu > 30 s → retour `RAW` et
   analyse avant de retenter.
4. **Testez le fail-safe** : coupez le nœud compteur → `Source Active`
   doit passer UDP → HA → FAILSAFE et la charge se bloquer en
   ~10 s. C'est le comportement attendu, pas un bug.
5. Testez le **kill-switch maître** : OFF = la borne retrouve son
   comportement d'usine (publication 0 A = marge maximale), sans toucher
   au câblage.

> Note - comportement au démarrage : le sélecteur **survit au reboot**
> (`restore_value`) et le firmware est **livré avec `ACTIF-MAX` en
> position initiale**. C'est un choix assumé pour un site en production :
> après une coupure de courant, le nœud doit revenir en train de
> RÉGULER, pas en observation. Conséquence pour une PREMIÈRE
> installation : au tout premier boot, le nœud est déjà en `ACTIF-MAX` -
> sans danger électrique (la loi clampe sous votre limite d'abonnement),
> mais cela court-circuite l'échelle de tests ci-dessus. D'où la
> consigne en tête de section : passez en `RAW` immédiatement après le
> flash, et ne revenez en `ACTIF-MAX` qu'une fois l'ombre validée. Une
> fois en production, le mode choisi est conservé à travers les reboots.

## 7. Attention véhicule : l'abandon silencieux

Après ~3 démarrages de charge perturbés en quelques minutes, le véhicule
Tesla **cesse de retenter** - sans aucune alerte côté borne (signature :
`evse_state` 9). Relance via l'app ou débranchement/rebranchement. Si vos
premiers essais multiplient les arrêts/reprises, c'est probablement ça -
pas une panne. Détails : [`BEHAVIOR.md`](BEHAVIOR.md) §5.

## 8. En cas de problème

| Symptôme | Piste |
|---|---|
| Octets RX mais zéro trame Modbus valide | polarité A/B permutée |
| `TWC Polling Active` OFF pendant que le RX défile | logs VERBOSE actifs → repasser en DEBUG |
| La borne ne bride jamais | limites Tesla One (§4) - Max Output Current puis Conductor Limit |
| Cadence mesure ~15 s, borne qui pompe | `rx_buffer_size` trop petit côté TIC |
| Charge refuse de démarrer sans raison | biais appliqué > 0 (capteur dédié) ou fail-safe actif |
| « Le DPM ne marche pas » vu depuis l'app du véhicule | capteurs cloud figés - regardez les vitals locaux |

Pour ouvrir un ticket : version du firmware TWC **obligatoire**, plus
carte, mode de signal, et capteurs d'observabilité
(voir [`../CONTRIBUTING.md`](../../CONTRIBUTING.md)).
