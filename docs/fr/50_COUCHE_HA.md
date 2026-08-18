# Tesla LoadPilot - couche Home Assistant, vue d'ensemble

> Le firmware (module 1) est autonome et suffisant pour la protection : sans
> HA, le fail-safe bloque la charge et le DPM protège l'abonnement. La couche
> HA ajoute l'intelligence : régulation douce, priorités, confort, voix.
> Référence complète (Loupiac) : package `contrat_electrique.yaml`
> (~6 200 lignes, 11 automatisations) + doc interne
> `contrat_electrique_LOGIQUE.md` (24 leçons numérotées). Ce fichier en
> donne la carte - et distingue le GÉNÉRALISABLE du spécifique Loupiac.

## 1. Architecture : 4 étages à kill-switches indépendants

| Étage | Rôle | Généralisable ? |
|---|---|---|
| 1. Alerte | annonce vocale + push critique + logbook sur dépassement soutenu (seuils %, durées, anti-rafale paramétrables) | OUI (remplacer le canal audio) |
| 2. Régulation véhicule | contrôleur granulaire continu (consigne API véhicule [min..plafond]) + pause/reprise + **levier biais borne** | cœur OUI ; la partie API Fleet est spécifique Tesla-propriétaire |
| 3. Délestage | coupure hiérarchisée d'équipements (priorités, filtre par phase, mémoires, restauration) | patron OUI ; équipements/phases = par installation |
| 4. Signal compteur | bit 7 du registre STGE Linky (« dépassement EN COURS » constaté par le compteur) → escalade immédiate qui traverse les 3 étages | FR seulement (équivalents à chercher par pays) |
| Dernier recours | suggestion vocale à l'humain quand plus aucun levier automatique n'existe | OUI |

Ordre émergent en dépassement : **le véhicule absorbe d'abord** (seul levier
fin), le délestage attend qu'il soit épuisé, l'humain n'est sollicité qu'en
dernier.

## 2. « Voiture d'abord, toujours » - et le levier binaire invité

Règle cardinale issue de la chronologie B (`40_LOI_DE_COMMANDE.md`) : le DPM
redistribue au véhicule toute marge libérée par une coupure d'équipement →
couper le confort pendant une charge est inutile. L'étape 0 de tout
délestage est donc la RÉDUCTION DU VÉHICULE, par le canal disponible :

| Situation | Levier | Modalité |
|---|---|---|
| Véhicule du foyer, API fraîche | consigne API (`number` courant de charge) | **proportionnelle** (la voiture obéit à une consigne : descente calculée, remontée bornée) |
| Véhicule invité / API périmée / API muette | **biais borne** (number ESPHome) | **BINAIRE** : pause = biais plein (16 A en triphasé, 32 A en monophasé) direct, relâche = biais 0 direct - jamais de valeur intermédiaire (loi de commande §2-3) |

Le canal binaire s'accompagne de :
- **mémo de demande** : AVANT la pause, mémoriser la demande du véhicule
  (max fenêtré 2 min du courant borne) - c'est ce qui reviendra au
  redémarrage (mémoire d'ampères par lieu Tesla) ;
- **relâche conditionnée à une PROJECTION** : biais 0 uniquement si la
  maison a la place pour le retour de la PLEINE demande mémorisée (place
  moyenne ≥ memo + 1 A ET marge pire phase ≥ memo) - sinon **la pause
  TIENT, même si tout est calme (le calme vient justement de la pause)**,
  avec notification expliquant à l'utilisateur comment reprendre (« réglez
  ≤ Y A dans le véhicule PENDANT une charge stable ») ;
- **garde anti-yo-yo** : 2 ouvertures de contacteur en < 3 min = oscillation
  DPM certaine (période ~55 s) → re-pause immédiate + blocage de relâche
  30 min ;
- **fin de session** : débranchement (`vehicle_connected` off, stable - les
  fenêtres contacteur du DPM ne comptent pas) → biais 0 inconditionnel +
  purge des mémos (un biais résiduel briderait la session suivante) ;
- **filet « biais oublié »** : tick périodique sans kill-switch - biais > 0
  + calme prouvé 30 min + relâche projetée possible → remise à 0 ;
- **re-mesures anti-creux** : ne JAMAIS conclure « la place suffit » sur une
  lecture prise dans un creux de la dent de scie (projeter le retour du
  véhicule via le max 2 min, ou moyenner ≥ 60 s).

## 3. Le contrôleur granulaire (véhicule pilotable par API)

Boucle continue (tick 10 s, période effective 30 s) - points transposables :
- loi proportionnelle sur la **pire phase lissée** (~60 s) pour le confort ;
  décisions de pause/urgence sur la **brute** ; décisions d'escalade sur
  l'**attendue** = brute − effet de la commande **en vol** (feed-forward :
  chaque commande déclare son effet attendu, ce qui évite de re-couper un
  excès déjà traité pendant les 7-20 s de latence d'observation) ;
- plafond de charge = réglage utilisateur EXPLICITE, jamais écrit par les
  automatisations (la détection de « consigne manuelle » a été essayée et
  supprimée : elle adoptait des artefacts) ;
- vérification d'effet sur **la borne locale** (courant, ~10 s), JAMAIS sur
  l'API cloud du véhicule (poll ~10 min, se fige) ;
- budget de commandes API quotidien (API Fleet facturée), anti-cyclage des
  pauses, gel des hausses après signal compteur ;
- **7 modes** exposés dans un sensor (inactif / indisponible / suiveur /
  limite / plancher / pause / arrêt_externe) + modes de session
  (véhicule_invité, fleet_degrade, invité_probable) - c'est l'entrée d'état
  du délestage et du diagnostic ;
- **mode borne_seul** (debug/dégradé) : TOUTE la régulation véhicule passe
  par le biais borne, zéro commande cloud - utile pour tester le canal
  binaire avec le véhicule du foyer, ou vivre sans API.

## 4. Mode manuel

`input_boolean` « mode manuel biais » : ON = plus AUCUNE écriture
automatique du biais (toutes les automatisations écrivaines sont gardées) -
indispensable pendant les tests (3 « bras de fer » automatisation vs
réglage humain vécus avant son ajout). La purge de fin de session reste
EXEMPTE (le débranchement nettoie toujours). Garde codée en
`not is_state(..., 'on')` : entité absente = garde inactive (fail-open).

## 4bis. Limite manuelle de charge (plafond utilisateur)

Motif validé sur le site pilote le 18/08/2026. Un plafond de courant
choisi par l'utilisateur (indépendant de la consigne du véhicule), sans
jamais fabriquer un signal compteur décorrélé : ce raccourci, rapporté
par la communauté (« lire /vitals et publier des valeurs simulées »),
désactive la corrélation 1:1 et finit dans l'état de défiance décrit
dans BEHAVIOR §4. À la place, une boucle côté HA (10 s, écriture asymétrique : hausse immédiate, baisse 0,5 A par tick, kick anti-hystérésis) calcule

    biais_cible = marge pire phase + courant véhicule (vitals) − limite

et l'écrit dans le number de biais du nœud borne, qui applique sa
propre rampe. L'écho du compteur reste intact (les vitals ne portent
que sur l'offset lent), toutes les protections restent actives : la
limite agit comme un plafond, la voiture prend min(limite, place
laissée par la maison).

Statut : LIVRÉ dans l'intégration (axe B), avec trois capacités sœurs,
toutes opt-in (une entrée existante qui ne touche à rien garde le
comportement historique à l'octet près) :

- `number.loadpilot_charge_cap` (0 = auto) : le plafond ci-dessus,
  porté en boucle de 10 s dans le coordinator (logique pure dans
  `control.py`, tests pytest qui rejouent les traces du 17-18/08) ;
- trim automatique de convergence (option, défaut OFF) : kick de biais
  2 A transitoire après 3 min de contrainte peu profonde, redondance
  ordonnée avec le palier 2 du firmware (4 min), jamais en conflit ;
- `binary_sensor.loadpilot_meter_distrust` + issue Repairs : détecteur
  de défiance générique (publié >= L + 0,85 tenu 120 s, véhicule
  > 9 A), levée automatique ;
- enforcement des réglages de loi (options gain/excursion/traînée,
  vides par défaut) : repoussés au setup et à chaque redémarrage du
  nœud (un flash remet les numbers `restore_value: false` aux défauts,
  le trou que le YAML ne bouchait pas).

Prérequis commun : l'option `vehicle_current_entity` (mappage avancé),
une source locale du courant véhicule, par exemple le capteur REST des
vitals de la borne (poll 5 s, montage pilote) ou l'intégration
officielle Tesla Wall Connector (poll ~30 s, mode dégradé, garde de
fraîcheur 60 s). Sans elle, les entités restent indisponibles et le
trim inerte.

## 4ter. Amortisseur de pointe et annonces groupées (motif site, 18/08/2026)

Deux motifs de confort validés sur le pilote, complémentaires du plafond
et du trim :

- **Amortisseur de pointe** : quand la pire phase franchit (seuil de
  pause − 4 points) pendant 8 s avec une charge active, poser
  immédiatement un biais = min(courant véhicule − 6, 6) A. La traction
  s'engage avant que le délestage n'atteigne son seuil de pause :
  l'épisode se règle par réduction, pas par coupure, et le véhicule
  n'envoie plus de notification « charge interrompue ». Relâche par
  l'amortisseur lui-même (2 min sous seuil − 8, seulement si le biais
  est encore le sien) ; le filet de rattrapage reste en second rideau.
- **Fenêtre d'annonce dynamique** : le délai anti-doublon des annonces
  passe de 2 à 20 minutes dès que deux pauses tombent dans la fenêtre
  d'hystérésis « repas », et revient à 2 minutes après 15 minutes de
  calme : une annonce par épisode de consommateur cyclique, pas une par
  cycle. Les chemins critiques ne portent pas cette garde.
- **Règle d'empilement des écrivains de biais** (indispensable dès que
  plusieurs boucles existent) : pause délestage > amortisseur > plafond
  manuel > trim ; chaque écrivain n'agit que si le biais vaut 0 ou sa
  propre valeur mémorisée.

## 5. Notifications

Patron transposable : une notification de SITUATION par épisode (annonce +
push critique, avec les mesures prises OU l'action demandée à l'humain),
actions ordinaires en logbook seul, notifications PERMANENTES à id fixes
avec mini-historique (stockage en codes courts ≤ 255 caractères, dépliage
par macro Jinja au rendu), anti-rafales partout - « les critiques passent
toujours » est un piège : pendant une dent de scie DPM, cela émettait une
critique par franchissement (10 en 9 min vécues) → UNE critique par épisode.

## 6. Spécifique Loupiac (à NE PAS publier tel quel)

- La carte des phases (quels équipements sur quelle phase) et les 6
  équipements délestables avec priorités/gains mesurés ;
- le délestage AGA/chauffe-eau (suggestion humaine phase 1) ;
- le chef d'orchestre audio Sonos, les groupes WhatsApp, les libellés
  français des annonces ;
- l'historique des recharges (package séparé, ventilation tarifaire
  Tempo) ;
- la télémétrie borne enrichie (package REST sur l'API locale de la borne :
  `/api/1/vitals` 2 s, `/api/1/lifetime` 10 min, `/api/1/version` 6 h -
  le PATRON est publiable, décodage `evse_state` sourcé communauté) ;
- les entités nommées (`whale_*`, `olimex_portail_*`…) → à renommer en
  placeholders dans tout exemple publié.

## 7. Leçons HA généralisables (sélection des 24 de la doc interne)

1. Un trigger `for:` perd son chrono au reload d'automations → tout pattern
   critique double son trigger d'un tick de rattrapage qui REPROUVE la durée
   via `last_changed`.
2. Ne jamais conditionner l'engagement d'un contrôleur sur une grandeur
   qu'il influence lui-même (deadlock vécu).
3. Toute temporisation persistante dans un `input_datetime` écrit par nous
   (les `last_changed` sont réinitialisés par les reloads).
4. Mémoire d'action posée AVANT la commande, retirée seulement sur échec
   vérifié (sinon : pause « orpheline » jamais reprise).
5. Plateformes non rechargeables (`filter`, `statistics`, `rest:`) → lissage
   en template à déclencheur (buffer en attribut), rechargeable à chaud.
6. `context.parent_id` vide = action humaine (UI/app/télécommande) - le
   critère du « rallumage manuel » qui lève les mémos de délestage.
7. Capteurs dérivés TOUJOURS avec `availability` (un 0 transitoire d'ESP au
   boot n'est jamais un retour au calme).
