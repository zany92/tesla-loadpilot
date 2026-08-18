# Guide d'installation - France (Linky, téléinfo TIC)

> Parcours complet pour l'installation de référence : Linky en mode TIC
> standard, nœud compteur Olimex ESP32-POE + hat Hallard, nœud borne
> Kincony KC868-A6, Tesla Wall Connector Gen 3 (firmware ≥ 26.18).
>
> Les paquets ESPHome génériques (`esphome/packages/`), les fichiers
> d'entrée prêts à copier (`esphome/examples/`) et l'intégration HACS
> (`custom_components/loadpilot/`) sont tous livrés dans ce dépôt et
> publiés en même temps sous un même tag. Les étapes matérielles, le
> commissioning Tesla One et les pièges sont vécus et validés en
> production sur le site pilote.
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

Copiez `esphome/secrets.yaml.example` vers votre `secrets.yaml` ESPHome
(Device Builder : menu en haut à droite > *Secrets editor* ; CLI : un
fichier `secrets.yaml` à côté de vos YAML de nœud) et renseignez les
**6 clés** :

| Clé | Contenu | Comment la générer |
|---|---|---|
| `loadpilot_api_key` | Clé de chiffrement de l'API native ESPHome (base64, 32 octets) | `openssl rand -base64 32` sur n'importe quelle machine, ou reprenez la clé qu'ESPHome génère à la création d'un appareil (affichée sous `api: encryption: key:`) |
| `loadpilot_ota_password` | Mot de passe des mises à jour OTA | n'importe quel mot de passe robuste, ex. `openssl rand -hex 16` |
| `loadpilot_udp_key` | **Clé UDP partagée** : elle chiffre les mesures (XXTEA) entre les deux nœuds. Elle DOIT être strictement identique sur le nœud compteur et le nœud borne | n'importe quelle phrase aléatoire longue, ex. `openssl rand -hex 16` ; collez la MÊME valeur une seule fois, les deux nœuds la lisent dans le même `secrets.yaml` |
| `loadpilot_wifi_ssid` | Réseau WiFi du nœud borne | votre SSID |
| `loadpilot_wifi_password` | Mot de passe WiFi | votre mot de passe |
| `loadpilot_ap_password` | Mot de passe du hotspot de secours du nœud | un mot de passe dont vous vous souviendrez devant le tableau |

Le fichier `secrets.yaml` **ne se commite jamais**
(voir [`../SECURITY.md`](../../SECURITY.md)).

### Flasher les nœuds : Device Builder ou CLI (à lire une fois, avant les sections 2 et 3)

Les deux nœuds se flashent de la même façon ; seul le fichier YAML
change. **L'ordre compte : flashez d'abord le nœud COMPTEUR**, vérifiez
que ses 6 grandeurs remontent, **puis le nœud borne** - le nœud borne
juge le flux UDP à sa fraîcheur, il lui faut donc un nœud compteur
vivant pour sortir du fail-safe.

**Voie (a) : ESPHome Device Builder (le module complémentaire Home
Assistant, la plus simple).**

1. Installez le module : Paramètres > Modules complémentaires >
   Boutique > « ESPHome Device Builder » > Installer > Démarrer, puis
   ouvrez son interface web (barre latérale).
2. Remplissez le *Secrets editor* (menu en haut à droite) selon le
   tableau ci-dessus.
3. Cliquez *+ New device* > donnez le nom du nœud (`loadpilot-meter`
   pour le nœud compteur) > passez l'assistant automatique quand il se
   propose (« Skip ») : vous allez coller une config complète à la
   place.
4. Sur la carte du nouvel appareil : menu (trois points) > *Edit*,
   effacez le contenu généré et collez l'exemple correspondant de
   [`esphome/examples/`](../../esphome/examples/)
   (`meter-teleinfo-olimex-poe.yaml` pour le nœud compteur,
   `charger-kc868-a6.yaml` pour le nœud borne), ajustez les
   substitutions (limite de contrat, disjoncteur, noms de nœuds),
   *Save*.
5. **Premier flash par USB** : reliez la carte à la machine qui fait
   tourner le navigateur, menu de la carte > *Install* > *Plug into
   this computer* > choisissez le port série. Si le port n'apparaît
   jamais ou si le flash échoue aussitôt, maintenez le bouton **BOOT**
   de la carte en branchant le câble USB (ou maintenez BOOT et pressez
   brièvement RST/EN), puis réessayez : la plupart des cartes ESP32 en
   ont besoin pour entrer en mode bootloader.
6. **Tous les flashs suivants se font en OTA** : *Install* >
   *Wirelessly*. Ni câble, ni bouton BOOT. Rappel de la section 0 :
   jamais d'OTA du nœud borne pendant une charge en cours.

**Voie (b) : la CLI `esphome` (aucun Home Assistant requis pour
flasher).**

```bash
pip install esphome            # une fois, Python 3.10+
cd <dossier avec vos yaml + secrets.yaml>
esphome run meter-teleinfo-olimex-poe.yaml     # compile + flash + logs
```

`esphome run` propose USB ou OTA quand les deux sont possibles ;
`esphome logs <fichier>.yaml` affiche ensuite les logs du nœud. Le même
`secrets.yaml` se place dans le même dossier que les fichiers YAML.

**Piège sur les petites machines (mesuré sur le pilote) : UNE seule
compilation à la fois.** Deux compilations ESPHome simultanées ont fait
planter la machine de build - les paquets livrés fixent d'ailleurs
`compile_process_limit: 1`. Compilez le nœud compteur, attendez la fin,
puis compilez le nœud borne ; jamais les deux en parallèle sur un hôte
type Raspberry.

## 2. Nœud compteur (Olimex ESP32-POE + hat Hallard)

### Pourquoi ce matériel : Olimex ESP32-POE + hat TIC

Le nœud compteur vit à côté du tableau électrique, un endroit pauvre en
prises de courant et (souvent) mal couvert en WiFi. L'**Olimex
ESP32-POE** règle les deux d'un coup : le **Power over Ethernet, c'est
UN seul câble** qui apporte à la fois l'alimentation et le réseau, et
l'Ethernet filaire est bien plus fiable que le WiFi dans une gaine
technique métallique. C'est du matériel open source avec un UART libre
pour la TIC. Achat chez
[Olimex](https://www.olimex.com/Products/IoT/ESP32/ESP32-POE/open-source-hardware)
(un switch ou injecteur PoE à l'autre bout du câble l'alimente ; l'USB
convient aussi si vous avez une prise).

Le **hat Hallard « WeMos TeleInfo »** est le récepteur TIC : il adapte
et **opto-isole** la sortie téléinformation du Linky (bornes **I1/I2**)
en un signal UART propre pour l'ESP32. Il lit la TIC en mode standard à
**9600 bauds, 7E1**, et arrive sur **RX GPIO36** une fois monté sur le
port UART de l'Olimex. Vendu assemblé :
[design sur GitHub](https://github.com/hallard/WeMos-TIC),
[Tindie](https://www.tindie.com/products/25467/),
[Lectronz](https://lectronz.com/products/wemos-tic).

Pièges connus de ce couple (détails :
[`10_MATERIEL.md`](10_MATERIEL.md)) :

- **`power_pin: GPIO12` doit rester dans le bloc Ethernet** : c'est le
  GPIO qui alimente le PHY LAN8720 ; sans lui, l'Ethernet peut ne
  jamais revenir après un soft-reset sur certaines révisions de carte
  (l'exemple livré le déclare) ;
- **`rx_buffer_size: 1024` obligatoire** sur l'UART TIC (une trame
  Tempo dépasse 400 octets ; voir les vérifications ci-dessous) ;
- n'importe quel ESP32 avec un UART libre peut remplacer l'Olimex, mais
  vous perdez l'argument du câble unique PoE et vous revalidez le bloc
  réseau vous-même.

### Assemblage et flash

1. **Câblage TIC** : deux fils entre les bornes **I1/I2** du Linky et
   l'entrée TIC du hat Hallard (opto-isolée, pas de polarité critique sur
   ce hat). Le hat se monte sur le port UART de l'Olimex - **RX GPIO36**,
   9600 bd, 7E1, mode standard.
2. **Réseau** : l'ESP32-POE s'alimente et se connecte en Ethernet (PoE ou
   USB). La config déclare `power_pin: GPIO12` (alimentation du PHY
   LAN8720) - sans lui, l'Ethernet peut ne pas revenir après un soft-reset
   sur certains exemplaires ([`20_FIRMWARE.md`](20_FIRMWARE.md) §1.2).
3. **Flash** : suivez le pas-à-pas de la section 1 (« Flasher les
   nœuds ») avec le fichier d'entrée d'exemple
   [`esphome/examples/meter-teleinfo-olimex-poe.yaml`](../../esphome/examples/meter-teleinfo-olimex-poe.yaml)
   (il consomme `esphome/packages/providers/teleinfo-fr.yaml` en paquet
   distant ; gardez `ref:` épinglé sur un tag de release, jamais
   `main`). Premier flash par USB, ensuite OTA.
4. **Vérifications** :
   - les 6 grandeurs (IRMS1-3, SINSTS1-3) remontent dans HA et varient ;
   - piège n°1 : **`rx_buffer_size: 1024` obligatoire** (une trame Tempo
     standard dépasse 400 octets ; à 256, 2 trames sur 3 se perdent et la
     cadence effective tombe à ~15 s → la borne pompera) ;
   - en Tempo, vérifiez que la cadence reste ~1 Hz.

En monophasé (THÉORIQUE - jamais validé sur banc) : un Linky monophasé
n'émet pas les étiquettes indexées que lit ce provider (SINSTS1/2/3) -
utilisez le provider dédié
`esphome/packages/providers/teleinfo-fr-mono.yaml` via l'entrypoint
`esphome/examples/meter-teleinfo-mono-olimex-poe.yaml` (`SINSTS` sans
indice + `URMS1` ; phases B/C publiées à 0, asservies au watchdog TIC).
Avec le provider triphasé, le flux UDP ne deviendrait jamais frais et le
nœud borne resterait en fail-safe pour toujours.

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
3. **Flash** du firmware nœud borne (pas-à-pas en section 1, « Flasher
   les nœuds » : premier flash USB, `secrets.yaml` renseigné) avec le
   fichier d'entrée d'exemple
   [`esphome/examples/charger-kc868-a6.yaml`](../../esphome/examples/charger-kc868-a6.yaml)
   (il consomme `esphome/packages/twc-core.yaml` +
   `esphome/packages/boards/kc868-a6.yaml` en paquets distants épinglés
   sur un tag de release). Alternative économique : la Kincony ESP32-S3
   Core Board dispose d'un board pack à l'état d'ébauche
   (`esphome/packages/boards/esp32-s3-core.yaml`,
   `board: esp32-s3-devkitc-1`) qui compile mais n'a JAMAIS été validé
   face à une borne ; un devkit ESP32-S3 nu demande en plus un
   transceiver RS485 externe type MAX485/MAX13487.
4. **Substitutions à ajuster à VOTRE installation** :
   - limite de contrat par phase (ex. 15 kVA tri : 5 000 VA / 230 V ≈ 21 A) ;
   - disjoncteur de branchement (`main_breaker`) - c'est la valeur publiée
     en fail-safe pour bloquer la charge ;
   - buffer de sécurité (défaut 10 %) ;
   - nombre de phases (`phase_count`) : `"3"` par défaut (référence
     triphasée). Une installation monophasée part plutôt de
     `charger-mono-exemple.yaml` (`phase_count: "1"`, plafond de biais
     `bias_max_a: "32"`) et s'associe au provider compteur monophasé
     (section 2) - THÉORIQUE, voir l'encart monophasé de la section 4.
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
     Sur le site pilote, une simple paire torsadée d'un câble Ethernet
     fonctionne parfaitement sur 2 m (non blindée, non terminée).

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

### Commissioning monophasé (THÉORIQUE - jamais validé sur banc)

Pour une installation monophasée (`charger-mono-exemple.yaml` +
`teleinfo-fr-mono.yaml`), le parcours Tesla One diffère sur trois points :

- **Type de réseau** : sélectionnez *monophasé* au commissioning du
  compteur Neurio (le libellé exact dépend de la version de Tesla One).
- **Max Conductor Limit** : dimensionné pour la phase unique, par ex. 32 A
  (un TWC Gen 3 mono débite jusqu'à 32 A sur sa seule phase).
- **Échelle de mise en service** : OMBRE-MAX d'abord, observation via
  `Shadow Published Current`, et séjour en RAW le plus court possible - en
  RAW les voies B/C publient ~0 constant, un signal mort si la borne
  moyenne ses registres CT.

Tout ce qui précède est THÉORIQUE : quels registres CT une borne
commissionnée en monophasé lit réellement, et si elle tolère des CT2/3 non
nuls, sont les premiers points de banc ([`TESTPLAN.md`](TESTPLAN.md), cas
monophasés). Les constantes de la loi de commande sont des mesures
triphasées.

## 5. Intégration Home Assistant (HACS)

L'intégration s'installe depuis ce dépôt en **dépôt personnalisé
HACS**. Pas de captures d'écran ici, donc chaque écran est décrit.

**Prérequis** : [HACS](https://hacs.xyz/) lui-même est installé et
visible dans la barre latérale de Home Assistant. Sinon, suivez d'abord
la documentation de HACS.

1. **Ouvrez HACS** depuis la barre latérale. Vous arrivez sur la liste
   principale de HACS.
2. **Ouvrez le menu débordant** : le **bouton trois points en haut à
   droite** de la page HACS > choisissez **Dépôts personnalisés**
   (*Custom repositories*). Une boîte de dialogue s'ouvre avec deux
   champs.
3. **Ajoutez le dépôt** : dans le champ *Dépôt*, collez
   `https://github.com/zany92/tesla-loadpilot` ; dans le champ *Type*
   (catégorie), sélectionnez **Integration** ; cliquez **Ajouter**. Le
   dépôt apparaît dans la liste de la boîte de dialogue ; fermez-la.
4. **Téléchargez l'intégration** : de retour sur la liste HACS,
   cherchez **« Tesla LoadPilot »** (parfois déjà mis en avant comme
   « Nouveau dépôt »). Ouvrez sa fiche : la description du dépôt
   s'affiche avec un bouton **Télécharger** en bas à droite. Cliquez
   *Télécharger* et confirmez la version (prenez la dernière release ;
   le `ref:` du firmware de vos nœuds doit pointer sur le MÊME tag).
5. **Redémarrez Home Assistant** : Paramètres > Système > menu
   d'alimentation en haut à droite > *Redémarrer Home Assistant*. Une
   intégration personnalisée n'est chargée qu'au démarrage ; ce
   redémarrage n'est pas optionnel.
6. **Ajoutez l'intégration** : Paramètres > Appareils et services >
   bouton **+ Ajouter une intégration** en bas à droite > cherchez
   **« Tesla LoadPilot »** > ouvrez-la. Le config flow en 5 étapes
   démarre : profil pays, les noms des deux nœuds ESPHome (validés
   contre votre registre d'entités), les réglages électriques (phases
   1|3, préréglage d'abonnement ou limite par phase personnalisée,
   tampon de sécurité), les 6 entités miroir (courant/puissance par
   phase : la source de SECOURS quand l'UDP se tait), et un écran de
   confirmation qui affiche le budget calculé.

L'intégration écrit les réglages **résidents sur le nœud borne**
(limite, buffer, biais, kill-switch) : un reboot de HA ne change rien à
la borne, et la régulation vit sans HA. Elle signale par une
*Réparation* HA tout écart de version firmware/intégration (les deux
canaux s'installent sur le **même tag**).

### Installation manuelle (secours sans HACS)

1. Téléchargez ce dépôt (git clone, ou GitHub *Code > Download ZIP*).
2. Copiez le dossier `custom_components/loadpilot/` entier dans votre
   répertoire de configuration Home Assistant, pour obtenir au final
   `config/custom_components/loadpilot/manifest.json`.
3. Redémarrez Home Assistant, puis ajoutez l'intégration comme à
   l'étape 6 ci-dessus. Vous n'aurez PAS de notification de mise à
   jour : surveillez vous-même la page des releases.

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
