> 🇬🇧 [English version](../en/BEHAVIOR.md)

# Gestion de charge TWC Gen 3 : modèle de comportement mesuré

> **C'est la valeur du projet.** Rien de ce qui suit n'est documenté par
> Tesla : tout a été mesuré sur une installation réelle (firmware borne
> **26.18**, triphasé 15 kVA, Max Conductor Limit 21 A, mesures Linky à
> ~1 Hz, vitals borne échantillonnés toutes les 2 à 8 s, plusieurs centaines
> d'échantillons, **57 épisodes de coupure contacteur ré-analysés au
> recorder** les 13-17/08/2026). Ces constantes sont des propriétés du
> couple firmware borne + véhicule : **à recalibrer si le firmware TWC
> évolue.**
>
> Chaque énoncé est marqué **MESURÉ** (nos données), **INFÉRÉ** (déduit,
> non testé directement) ou **RAPPORTÉ** (source externe). Cette page est
> la traduction du condensé anglais du document de référence français,
> [`40_LOI_DE_COMMANDE.md`](40_LOI_DE_COMMANDE.md) : en cas de divergence,
> c'est ce dernier (17/08/2026, modèle définitif) qui prévaut.

La borne exécute deux mécanismes indépendants sur le signal compteur
qu'elle interroge en Modbus (cycle ~190-200 ms) : une **boucle de
service** lente qui module le signal pilote offert au véhicule, et une
**protection** rapide qui mord puis finit par ouvrir le contacteur.

## 1. Boucle de service : une fonctionnelle SYMÉTRIQUE des 3 voies publiées

La boucle de service ne regarde **pas** la pire phase publiée :

- **MESURÉ** : ≥ 20 épisodes de coupure discriminants (publication par
  phase différenciée, max > 21 A, moyenne < 21 A) sans **aucune**
  modulation de service préalable : le véhicule reste strictement constant
  jusqu'à la coupure de protection. ~6 minutes cumulées de `max > 21` avec
  `moy < 21` sur les épisodes des 13-14/08 (ex. 3 min à 8,1 A constants
  avec une voie publiée à ≈ 22 A en continu). Même un service par phase
  lent (1-2 A/min) aurait produit une dérive visible : absente partout.
- **MESURÉ** : l'engagement du service n'a été observé **que lorsque la
  moyenne des 3 voies publiées franchit la limite** (17/08 00:36-00:42 :
  aucune réaction à moyenne 20,6-20,9 malgré des maxima 21,3-22,4 ;
  modulation dès moyenne ≥ 21,3 ; récupération dès moyenne < 20).
- **Ambiguïté résiduelle (non tranchée)** : moyenne vs min-des-publiés.
  Tous nos épisodes différenciés avaient min ET moyenne < 21
  simultanément ; en publication symétrique les trois coïncident. **Sans
  incidence en publication symétrique** (toute fonctionnelle symétrique
  s'engage au même point). Le test académique qui aurait tranché (2 voies
  ~22 / 1 voie ~18 sous clamp) a été conçu mais jamais exécuté.
- **RAPPORTÉ (convergent, plusieurs sources fw 26.x)** : loin de la
  limite, la dynamique de service est **LENTE, en minutes** : une
  « trajectoire » incrémentale autour de la limite configurée, pas un
  asservissement `setpoint = f(CT)`. Les descentes prennent des minutes
  même à disponibilité nulle, d'où la technique d'escalade (« publier
  +0,1 au-dessus de la limite ») pour forcer un arrêt. PVi1 lui-même
  documente « ramps down very slowly (minutes) ».
- **MESURÉ** : près de la limite, la réaction est courte : ~5-20 s entre
  le franchissement de la moyenne et le premier mouvement du pilote (19 s
  au clamp lors de la validation du 17/08).
- **MESURÉ (17/08)** : pas de décréments fins de ~1 A à la descente ; la
  **remontée** après retour d'une marge franche est autonome et cadencée à
  **~1 A / 30 s** (11 → 16 A en ~2 min).
- **RAPPORTÉ (externe, important)** : personne, PVi1 compris, n'a
  démontré la loi de service exacte. Le « min par phase » de PVi1 est une
  inférence auto-rapportée à partir de 1-2 épisodes vécus (« not
  officially confirmed by Tesla, just inferred from testing »), sans logs
  bruts publiés ; nos épisodes courts (43 s à 3 min) l'excluent comme loi
  rapide. La tension d'échelle de temps reste non résolue, une raison de
  plus pour publier symétrique.

## 2. Protection : PIRE PHASE, morsure puis coupure franche

Indépendante de la boucle de service, la protection est calée sur le **CT
maximum** (`max(CT1, CT2, CT3)` comparé à la Max Conductor Limit, 21 A
ici) :

- **Morsure (MESURÉ)** : un grignotage de 2-6 A du pilote, déclenché à
  max ≈ **21,3** (jusqu'à ~23), latence **≤ 5 s**, durée 5-10 s, avec
  **récupération complète** dès que l'excès instantané cesse, y compris
  pendant que la voie fautive reste > 21. Une morsure récupère ; un
  mouvement de service tient son palier : c'est le critère de distinction.
- **Coupure (MESURÉ, très haute confiance)** : le contacteur s'ouvre quand
  l'**intégrale d'excès pire phase** atteint **~20-21 A·s**
  (mesuré ≈ 21 A·s ; théorie ~20), l'intégrale **décroissant tant que la
  voie est repassée sous la limite**, ce qui explique les longues
  expositions tolérées à faible excès (55 s tolérées à ~21,8 observées
  historiquement). ≥ 20 coupures avec moyenne < 21 (jusqu'à moyenne
  11-16) et **zéro contre-exemple** exigeant moyenne ≥ 21 : la protection
  ne moyenne jamais.
- Durée `max > 21` la plus courte mesurée menant à une coupure : **43 s**.
- **Bande morte au-dessus de L (MESURÉ 17/08 au soir)** : la borne a
  toléré **~70 s à un publié L + 0,45..0,55 SANS la moindre réaction du
  pilote**, et une traction franche (descente nette et soutenue) n'a été
  observée qu'à partir de **≥ ~L + 0,9**. L'intégrale d'excès est tout
  aussi tolérante à +0,5 : **35 A·s accumulés à ce niveau sans coupure**.
  Conséquence pour le modèle : le **budget intégral de ~20 A·s de la
  coupure vaut pour des excès ≥ ~1 A** ; ne pas l'extrapoler linéairement
  dans la zone L+0,1..L+0,5, où service comme protection sont bien plus
  tolérants que ne le suggère le −1 A/s nominal de la micro-loi à
  L + 0,1. Toute escalade ou tout réglage de gain co-variant qui fait
  atterrir la valeur publiée dans cette bande morte est purement ignoré.

## 3. Plausibilité : corrélation 1:1, ne jamais diluer

Le firmware 26.18 vérifie que le signal compteur est corrélé à sa propre
sortie : pendant que la voiture charge, le courant publié doit **monter
d'autant**.

- **RAPPORTÉ (PVi1, mesuré sur son installation)** : diluer la composante
  véhicule (moyennage de phases, lissage EMA du signal publié) casse la
  corrélation → arrêt en quelques secondes. Un gain multiplicatif sans
  retard est accepté ; un retard temporel est rejeté.
- **MESURÉ (cohérent)** : toutes nos publications dans lesquelles le
  courant propre de la borne revenait en 1:1 ont été acceptées sans la
  moindre erreur de plausibilité ; les yo-yos observés avec notre variante
  à estimateur s'expliquent entièrement par l'estimateur lui-même (un
  fantôme de Linky en retard), pas par un rejet de la borne.
- Règle de conception : **le signal publié doit suivre le courant véhicule
  en 1:1, jamais dilué, jamais retardé sur cette composante.**
- **Le gain a un PLANCHER de plausibilité (MESURÉ 17/08 au soir, 20:30)** :
  la règle « ne jamais diluer » de PVi1 est désormais quantifiée sur notre
  installation : un adoucissement anti-yo-yo de la loi co-variante (gain
  0,5 → 0,25, emax 1,0 → 0,5) a produit un **gain effectif < ~0,5 sur la
  composante chargeur en contrainte** : une dilution 4:1, l'erreur du
  « moyennage » déguisée. Une seule rampe de démarrage du véhicule
  partiellement absorbée sous le plafond abaissé a suffi à **latcher la
  défiance en une seule rampe** (publié cloué de 21,45 → 21,85 pendant
  3 min pendant que la voiture restait figée à 12,1, pause biais-16
  ignorée). Règle : **ne jamais descendre le gain en contrainte sous
  ~0,5** ; traiter le yo-yo par la forme de la loi (variante B), jamais
  par le gain.

## 4. L'état de défiance : quand la borne cesse de croire le compteur

Le contrôle de plausibilité du §3 n'est pas qu'un filtre par échantillon :
lorsqu'il est violé, la borne entre dans un **état de défiance latché**
dans lequel le compteur émulé est durablement ignoré. **MESURÉ sur notre
installation (17/08/2026, deux épisodes instrumentés)** :

- **Chemin d'entrée n° 1 (MESURÉ)** : une valeur publiée **sous le courant
  propre de la borne** : un glitch compteur ponctuel a publié ~0,6 A sur
  une phase pendant ~2 s alors que la borne elle-même tirait 16 A. Un vrai
  compteur en tête d'installation ne peut physiquement jamais lire moins
  que la branche du chargeur : implausible au dernier degré ; la défiance
  semble s'être latchée à cet instant précis.
- **Chemin d'entrée n° 2 (MESURÉ)** : une **rampe véhicule absorbée par le
  clamp saturé** : la valeur publiée clouée à la limite (disponibilité
  nulle), la voiture est montée de 8 → 16 A alors que le signal publié
  n'a répercuté que +0,7 A : huit ampères du courant propre de la borne
  invisibles dans le compteur qu'elle interroge. Le contrôle de
  corrélation 1:1 casse ; la défiance de session a été immédiate. Notez la
  tension de conception : le clamp même qui rend le déclenchement
  impossible (§7) est ce qui absorbe l'écho de rampe en saturation
  prolongée. (Confiance intacte, ce recoin est inatteignable : à
  disponibilité nulle le pilote est bas, donc la voiture ne peut pas
  monter en rampe ; ce n'est arrivé que parce que la défiance était déjà
  installée.)
- **Une fois installée, la borne ignore TOUT (MESURÉ)** : plus de
  modulation de service au clamp soutenu, plus de morsures de protection,
  plus de coupure intégrale, et l'**escalade L + 0,1 a été ignorée pendant
  8 minutes** contacteur fermé : à 0,1 A au-dessus de la limite pendant
  480 s, l'intégrale de ~20 A·s (§2) aurait dû couper vers ~200 s si le
  compteur était encore honoré. La borne charge simplement à son plafond
  interne.
- **Ce qui ne la lève PAS (tout est MESURÉ)** : une renégociation du
  courant de charge, une session de charge toute neuve, un reboot du nœud
  émulant le compteur (~1 min de trou Modbus), un dither de ±0,05 A sur la
  valeur publiée.
- **Ce qui l'a levée, apparemment (MESURÉ une fois)** : une fenêtre
  nocturne pendant laquelle le nœud a publié pendant des heures **la
  mesure brute honnête** (mode ombre). Le lendemain matin, la confiance
  était revenue et la validation du §8 s'est déroulée sans accroc.
  **Hypothèse de travail (INFÉRÉ)** : la confiance est un **score**,
  reconstruit par le temps passé sur un signal plausible et corrélé 1:1,
  pas un drapeau événementiel. Un re-test contrôlé (1-2 h de signal
  honnête, puis ré-engagement) est en cours, et un détecteur horodate
  désormais chaque entrée/sortie de l'état.
- **« Honoré à l'arrêt, ignoré en session » CONFIRMÉ localement (MESURÉ
  17/08 au soir)** : la signature communautaire (§ Corroboration
  indépendante ci-dessous) est désormais mesurée sur notre installation :
  pendant un épisode de défiance de session, la **porte de démarrage de
  charge est restée pilotée par le compteur**. Le refus de démarrage à
  publié > L − 5 et l'acceptation à publié < L − 5 ont tous deux
  fonctionné exactement selon la micro-loi pendant que tous les ordres en
  session étaient ignorés. La défiance ne désactive donc que le chemin de
  régulation en session, pas le contrôle d'admission ; ce qui signifie
  aussi qu'un refus de démarrage n'est JAMAIS une preuve que la confiance
  est revenue.
- Invariant d'exploitation qui en découle : **ne jamais publier une valeur
  sous le courant propre de la borne, et ne jamais laisser le signal
  publié cesser de répercuter les rampes du véhicule**, même en
  saturation.

### Protocole de récupération (MESURÉ, 17/08/2026 au soir)

Le re-test contrôlé annoncé ci-dessus a été mené l'après-midi et la soirée
du 17/08. Bilan :

- **Ce qui a restauré la confiance (MESURÉ une fois, attribution
  partiellement confondue)** : la combinaison d'une **coupure secteur
  (power-cycle) de la borne** (disjoncteur off/on), puis **~2 h de signal
  publié honnête, corrélé 1:1** (mode ombre), puis un **premier démarrage
  de session maison calme** (pour que la rampe d'ouverture du véhicule
  soit intégralement répercutée, jamais absorbée par la saturation).
  Preuve dure : le **même ordre d'arrêt L + 0,1 ignoré pendant 8 minutes
  à midi a été exécuté en ~5 s le soir** (18:49:46, descente ~1 A/s), et
  toute la validation §8 du soir s'est ensuite déroulée sans accroc. La
  coupure secteur et la cure de signal honnête tombent dans la même
  fenêtre de récupération, leurs contributions individuelles ne sont donc
  **pas encore séparées** ; une coupure secteur seule avec une cure courte
  (< 1 h) a été testée et n'a PAS récupéré (mais la session post-reboot a
  démarré en saturation, ce qui a pu re-latcher la défiance à la seconde
  même). À affiner au prochain épisode de défiance.
- **Requalification de lectures « défiance » antérieures (MESURÉ)** :
  plusieurs épisodes lus jusque-là comme « la borne est sourde » avaient
  en réalité la valeur publiée **à ou sous L (≤ 21,0)**. C'est le HOLD
  nominal de la micro-loi (publié = L ⇔ tenir le palier de courant), pas
  de la défiance : un clamp À la limite ne peut pas commander une
  descente. **Seuls des ordres ignorés strictement au-dessus de L
  (≥ L + 0,1 soutenu) prouvent la défiance.** Tout détecteur de défiance
  doit donc se déclencher sur `publié > L` ignoré, jamais sur « pas de
  réaction à publié ≤ L » : notre premier seuil de détecteur (20,85) a
  produit exactement ce faux positif et a été recalibré (21,45).

### Corroboration indépendante (RAPPORTÉ)

- **PVi1 (TMC, 09/08/2026, fw 26.18, notre version exacte)** : arrive
  indépendamment à la même théorie : le TWC3 « actively checks whether
  the reported meter value actually correlates with the load it's causing
  itself » ; une valeur d'allure statique → détectée et ignorée,
  régulation honorée avant une session mais ignorée pendant. Son remède
  rejoint le nôtre : les CT doivent **mesurer une branche qui inclut la
  borne elle-même** pour que la valeur rapportée soit physiquement
  corrélée aux rampes de la voiture. Même fil : le verrou installateur sur
  le commissioning du compteur introduit vers la fw 26.2.0 est
  contournable sur 26.18 via un compte Tesla générique (app → More →
  « Tesla device settings »), et le plancher régulé est 5 A.
- **Klangen82, issue #1 de `tesla-wall-connector-control` (05/05/2026)** :
  un pas **permissif** de +1 A (10 → 11 A) de la valeur émulée pendant une
  session active : le TWC « often enters a 'fail-safe' mode before it
  starts ramping up to the new value ». La défiance peut donc se latcher
  sur toute discontinuité décorrélée du comportement de la borne, pas
  seulement sur des valeurs restrictives ou impossibles.
- **Klangen82 issue #7 (mitf559, Gen 3 flambant neuve ; et YLAG sur
  fw 25.x)** : la signature complète : compteur honoré à l'arrêt, ignoré
  en session, « the amps will ramp up to the max » quelques secondes après
  le début de la charge. YLAG rapporte la même chose sur **fw 25.x**.
- **Divergence d'interprétation (signalée, non tranchée)** : la communauté
  (avertissement du README de Klangen82 du 20/04/2026, repris ailleurs)
  attribue cela à un **« verrou fw 26.2+ »** qui « ignores external
  current limits during active charging ». Le faisceau d'indices plus
  large (fw 25.x touchée (YLAG), des installations 26.x qui fonctionnent
  ailleurs (FreekSchreurs : « Firmware version 26.x works without
  problem ») et notre 26.18 parfaitement pilotable) pointe plutôt vers un
  **état comportemental récupérable, présent depuis au moins la 25.x**,
  déclenché par le style de publication et non verrouillé par la version
  du firmware. Aucune des deux lectures n'est prouvée.

### Ce que Tesla documente officiellement (RAPPORTÉ, note d'application DPM, rév. 1.2, janvier 2024)

- En cas de **perte de connexion compteur**, le repli documenté est une
  **sortie maximale de 6 A** (« so as not to overload the system ») : un
  mode dégradé, pas un arrêt.
- **Aucun état « compteur ignoré » / défiance n'est documenté nulle part**
  dans la note d'application : le comportement décrit dans cette section
  est une couche non documentée.
- Max Conductor Limit = **80 % du calibre du tableau** ; **un seul Wall
  Connector par compteur** ; requiert **fw ≥ 23.8.1**. (Le plancher régulé
  de 5 A ci-dessus est le rapport de PVi1 sur 26.18, pas un chiffre de la
  note d'application ; notez qu'il diffère du repli documenté de 6 A en
  perte de compteur.)

## 5. Session : la mémoire du véhicule et l'abandon silencieux

Comportements côté véhicule (Tesla), mesurés à travers la borne :

- **Ampères mémorisés PAR LIEU (MESURÉ)** : à chaque redémarrage de
  session, le véhicule ré-applique sa consigne mémorisée pour le lieu
  (souvent 16 A), écrasant tout réglage fait au cours de la session
  précédente. Un réglage effectué *pendant* une charge stable, lui,
  persiste.
- **Abandon après ~3 sessions perturbées (MESURÉ, deux fois le 17/08)** :
  après environ trois démarrages de charge interrompus en quelques
  minutes, le véhicule **cesse de réessayer**. Signature exacte :
  `evse_state` → **9**, **zéro alerte côté borne**, compteur de cycles de
  charge figé : indiscernable d'une fin de charge normale vue de la borne.
  **Le redémarrage exige l'app** (ou un débranchage/rebranchage). Toute
  architecture à base de pause doit le prévoir : redémarrage automatique
  après relâche si une API est disponible, sinon une notification
  explicite ; et de l'anti-cyclage pour que cela n'arrive jamais.

## 6. Dynamique mesurée (constantes de calibration)

| Grandeur | Valeur mesurée |
|---|---|
| Morsure : latence après excès pire phase | ≤ 5 s |
| Morsure : amplitude / durée | 2-6 A / 5-10 s, récupération complète |
| Coupure : intégrale d'excès pire phase | ~20-21 A·s (décroît sous la limite) |
| Service : latence près de la limite (moyenne ≥ 21) | ~5-20 s |
| Service : remontée autonome à marge franche | ~1 A / 30 s |
| Service : dynamique loin de la limite | minutes (RAPPORTÉ, convergent) |
| Rampe de descente à une coupure | ~1 A/s |
| Rampe de remontée après ré-autorisation | ~0,65 A/s |
| Fenêtre contacteur ouvert dans un cycle | ~15-20 s |
| Période du bang-bang entretenu (publication RAW, gain de boucle 1) | ~55 s |
| Minimum véhicule (Tesla, AC triphasé) | ~6 A |
| `evse_state` pendant un arrêt de cycle / abandon véhicule | 11 → 7 / 11 → 9 |
| Effet d'un ampère de charge (triphasé) | ~230 VA par phase et par ampère |
| Cadence de poll Modbus de la borne | ~190-200 ms |
| Timeout de retry Modbus (délai limite de réponse) | ~66 ms |
| Réponse du véhicule à un changement de consigne J1772 | ~5 s |

## 7. La conséquence architecturale : publication symétrique pire phase clampée

> **Remplacé le 17/08/2026 au soir (flash n° 2)** : le clamp dur
> ci-dessous a été remplacé par la **loi co-variante**
> (`DESIGN_LOI_COVARIANTE.md`, variante A) après démonstration que le
> clamp lui-même fabrique l'état de défiance du §4 (une valeur plate
> saturée absorbe l'écho de rampe du véhicule). La loi co-variante
> conserve tout de cette section sauf le plat : hors contrainte, elle
> publie la réalité décalée telle quelle ; en contrainte, elle publie
> `L + clamp(gain × excess, 0.1, emax)` avec un dither permanent de
> ±0,05 : la valeur publiée n'est jamais morte, et le niveau au-dessus de
> L est lui-même le signal de ralentissement mesuré (L+0,1 → ~−1 A/s ; L
> exactement → HOLD ; sous L → remontée). Le déclenchement passe
> d'« impossible par construction » à « improbable par dynamique »
> (budget intégral de ~20 A·s contre des secondes d'exposition).
> Validation mesurée : §8, entrée du soir.

Ce fut le premier point d'atterrissage du projet, et il découle
mécaniquement des §1-§4 :

```
dispo_p  = budget − biais − mesure_p        (par phase, clampé [0 ; L])
publie_p = L − min(dispo_1, dispo_2, dispo_3)     (identique sur les 3 voies)
```

- **Service symétrique + protection pire phase + loi de service exacte
  inconnue ⇒ publier la PIRE PHASE À L'IDENTIQUE sur les 3 voies** : la
  seule publication robuste : min = moyenne = max par construction, donc
  la boucle de service s'engage exactement à la vraie contrainte **quelle
  que soit la fonctionnelle réelle** (moyenne, min-des-publiés ou autre).
- **Le déclenchement est impossible par construction** : la valeur publiée
  est clampée ≤ L (21 A) : la protection pire phase ne voit jamais
  d'excès ; morsures et coupures disparaissent. Une défaillance de ce bloc
  est un non-démarrage ou un pompage doux, jamais un claquement de
  contacteur.
- **Arrêt délibéré = escalade** : puisque la borne descend vers la
  « disponibilité nulle » en minutes (§1) et peut tenir un résiduel
  indéfiniment, après **120 s à disponibilité nulle** le bloc publie
  **L + 0,1** sur les 3 voies pour forcer un arrêt propre (technique de
  PVi1 : RAPPORTÉ, puis MESURÉ sur notre installation). Réserve :
  l'escalade n'est honorée que tant que le compteur est cru ; en état de
  défiance (§4), elle a été ignorée pendant 8 minutes mesurées.
- **Aucun estimateur véhicule** : la mesure publiée INCLUT le courant de
  la borne → le signal publié suit le véhicule en 1:1 et le contrôle de
  plausibilité (§3) est satisfait par construction. Aucun état interne
  hors le timer d'escalade (voir les résultats négatifs, §9 : chaque état
  interne ajouté avait créé son propre bug).
- **Tampon de sécurité** : la ressource offerte est
  `budget = contract_limit × (1 − b)` (b = 10 % par défaut) : le véhicule
  n'exploite jamais 100 % de la marge, en régime établi comme en
  transitoire.

## 8. Validation (17/08/2026, 11:21-11:35, trace 3 s, bloc ACTIF)

Base de cycles contacteur = 470. Véhicule à 16 A, maison vivante (clim,
pompe de piscine). **MESURÉ** :

| Heure | Événement | Publié (sym.) | Véhicule |
|---|---|---|---|
| 11:21-11:23 | régime établi | 18,1-18,3 | 16,0-16,1 stable |
| 11:23:42 | la clim démarre → **clamp à exactement 21,0** | 21,0 | 16,0 |
| 11:24:01 | première modulation douce (**19 s** après le clamp) | 20,3 | 16,0 → **15,1** |
| 11:26:03 | palier suivant (publié ~20,1 soutenu) | 20,1 | → **13,1** |
| 11:27:48-11:28:03 | pompe de piscine (publié 20,8-20,9) | 20,9 | → **11,1** |
| 11:28-11:30 | **palier 11,1 TENU ~2 min, zéro pompage** | ~19,1 | 11,1 |
| 11:29:34-11:30:00 | fin de l'appel domestique, le publié tombe de 15,4 → 13,6 | 13,6 | 11,1 |
| 11:30:03 → 11:32:03 | **remontée autonome ~1 A / 30 s** | 13,6 → 18,4 | 12,1 → … → **16,1** |
| 11:32-11:35 | régime établi retrouvé | 18,1-18,4 | ~16,0 |

Bilan : cycles contacteur **470, inchangés** (zéro coupure), **zéro
morsure**, `evse_state` = 11 en permanence, modulation douce à la descente
ET remontée autonome : **la borne 26.18 SAIT tenir un palier sous la
demande du véhicule** quand le signal publié est borné ≤ limite. Deux
échelons de charge domestique réels absorbés sans le moindre événement.

### Validation du soir : loi co-variante, flash n° 2 (17/08/2026, 19:06-19:43, MESURÉ)

La loi co-variante v2 (bandeau du §7) a été flashée à 19:06 et validée en
réel le soir même, avec la confiance fraîchement restaurée (protocole de
récupération, §4). Toutes les entrées ci-dessous sont **MESURÉES**
(traces 3 s `test_soir_v3.log`, `test_v2_covariant.log`,
`test_v2_toutes_clims.log`) :

- **La « danse d'équilibre » est le régime NORMAL de la v2 : ne pas la
  prendre pour de la défiance.** En publication co-variante, à la
  frontière du budget, le véhicule tient **±1 A autour de l'équilibre
  exact** (`budget − maison`, 15-16 A observés) pendant que la valeur
  publiée oscille autour de L (20,9-21,4 observés). C'est la loi qui
  travaille : chaque franchissement au-dessus de L est un vrai coup de
  frein, chaque retour sous L une vraie relâche. Notre premier détecteur
  de défiance (seuil 20,85) a signalé cette danse comme de la défiance :
  faux positif ; le critère recalibré porte sur des ordres *ignorés*
  au-dessus de L (21,45 / 120 s / véhicule > 9 A).
- **Descente continue sous contrainte soutenue (l'angle mort du clamp v1,
  corrigé).** Un échelon de charge de quatre climatisations a conduit le
  véhicule de **16 → 12+ A en une seule descente continue** sous une
  pente publiée à L + 0,95 (~21,95 observé) : aucun palier à 15 A, aucune
  valeur publiée figée, aucune entrée en défiance. La borne a suivi le
  signal d'excès compressé exactement comme la micro-loi le prédit.
- **Cascade complète démontrée de bout en bout sans intervention
  humaine** : descente du véhicule sous la loi → toujours insuffisant →
  pause de la couche HA posée à 45 s (biais 16 : le véhicule a été arrêté
  AVANT tout délestage d'équipement domestique, « la voiture d'abord »
  exécuté à la lettre) → fin de l'échelon de charge → biais relâché
  (16 → 0 instantanément, règle contacteur ouvert) → **reprise de session
  AUTONOME à la seconde même de la relâche** (cycle contacteur 478, aucune
  interaction avec l'app). L'abandon silencieux du véhicule (§5) ne s'est
  pas déclenché.
- Événements borne sur toute la soirée : les seuls cycles contacteur sont
  l'arrêt/redémarrage de session attendus de la cascade : zéro coupure de
  protection, zéro morsure, zéro entrée en défiance.

### Plus tard dans la soirée : le yo-yo en boucle fermée (MESURÉ 17/08, ~20:20)

La danse d'équilibre ci-dessus est bénigne, mais sous une contrainte
**soutenue** la loi v2 à gain 0,5 / emax 1,0 peut dégénérer en un
véritable cycle limite en boucle fermée :

- **Signature (MESURÉ)** : courant véhicule cyclant à **±2,5 A** avec une
  période de **~20 s**, la valeur publiée franchissant L à chaque
  excursion ; après **7 excursions**, l'intégrale d'excès pire phase (§2)
  a accumulé jusqu'au seuil de coupure et le **contacteur s'est ouvert**.
  Ce n'est pas de la défiance (chaque ordre a été honoré : c'est la
  boucle qui obéit trop bien) et ce n'est pas le bang-bang RAW de ~55 s
  du §6 : c'est une oscillation plus rapide, en forme de loi, propre au
  retour co-variant à ce couple de gains.
- **Ce qu'il ne faut PAS faire (MESURÉ, leçon apprise le soir même)** :
  baisser le gain pour l'amortir crée la dilution du §3 (plancher de
  gain) et latche la défiance : strictement pire. Gain 0,5 / emax 1,0
  reste le couple validé.
- **Statut** : le correctif en cours de conception est la **variante B**
  de la loi co-variante (réponse asymétrique / coups de frein un cycle
  sur deux, cf. `DESIGN_LOI_COVARIANTE.md`), qui remodèle le signal de
  descente au lieu de l'affaiblir. En attendant qu'elle atterrisse, un
  épisode de contrainte soutenue doit être résolu par la pause de la
  couche HA (biais), pas en laissant la boucle pomper.

## 9. Résultats négatifs (assumés, et publiés à dessein)

Une architecture antérieure, un « synthétiseur de signal » qui découplait
la composante AC du véhicule via un estimateur (gain α < 1 sur les
transitoires), a été entièrement conçue, implémentée, testée sur le
terrain plusieurs nuits durant et corrigée six fois avant d'être
**abandonnée le 17/08/2026** au profit du bloc sans mémoire ci-dessus.
L'étude complète et son épilogue post-mortem sont conservés intacts dans
[`60_ETUDE_SYNTHETISEUR.md`](60_ETUDE_SYNTHETISEUR.md). Points
saillants :

- **Schéma de défaillance structurel (MESURÉ)** : chaque correctif
  ajoutait de l'état interne, et chaque défaillance suivante était un
  mode transitoire de l'état ajouté par le correctif précédent. Bilan
  final : ~20 globales de contrôle dynamiques dans la dernière variante
  du synthétiseur, contre **une** (le timer d'escalade) dans le bloc sans
  mémoire qui l'a emporté.
- **La cause racine était l'estimateur lui-même** : séparer « maison » et
  « véhicule » à partir de vitals en retard de ~2 s, face à une borne qui
  décide toutes les ~200 ms et un véhicule qui rampe à ~1 A/s, engendre
  toute une classe de bugs de fraîcheur/gel/purge/ancrage. Une conception
  sans estimateur n'en a structurellement aucun.
- **Une perle forensique (MESURÉ à 0,1 A près)** : l'API native d'ESPHome
  **déduplique les états de capteur identiques** avant transmission, si
  bien qu'un heartbeat Home Assistant avec `force_update: true` n'atteint
  jamais le nœud. Une garde de fraîcheur de 10 s a donc déclaré « mort »
  un courant véhicule parfaitement *stable* : chaque palier ≥ 10 s (le
  but même de la régulation) effondrait le signal publié de −7,3 A à
  entrées physiques constantes. Prouvé par trois indices indépendants,
  dont une phase immunisée par un dither accidentel 13,0↔13,1.
- **Le verdict antérieur du « plafond firmware » a été re-périmétré** :
  « la borne ne tient jamais un palier sous la demande » n'est vrai **que
  pour la publication RAW auto-référente (gain de boucle 1)** : une
  boucle discrète marginalement stable de multiplicateur −1. C'était la
  signature du gain de boucle, pas un plafond firmware. Corollaire :
  au-delà de ~1 Hz, la fraîcheur de mesure n'apporte rien (0,46 s testé,
  sans aucun changement en RAW) : les clamps CT sous la seconde sont
  inutiles à cette fin.

À notre connaissance, ce corpus (service symétrique / protection pire
phase / plausibilité 1:1, la table des six défaillances, le piège de
déduplication de l'API et la loi « chaque état interne crée son propre
bug ») est la caractérisation la plus complète de ce firmware de borne
qui existe. C'est pourquoi les échecs sont publiés à côté du résultat.

## 10. Périmètre et avertissement de recalibration

Toutes les constantes ci-dessus ont été mesurées sur le **firmware TWC
26.18** avec un véhicule Tesla, sur une installation française triphasée
15 kVA. La *structure* de la loi (service symétrique, protection pire
phase, plausibilité) devrait tenir sur toute la 26.x (RAPPORTÉ, sources
communautaires convergentes), mais les *constantes* sont des données de
calibration. **Si le firmware de votre borne diffère, rejouez la
validation du §8 avant de faire confiance aux réglages d'escalade et de
tampon** ; et merci de rapporter vos mesures (voir `CONTRIBUTING.md` ; la
version du firmware TWC est obligatoire dans tout rapport).

---

*Crédits : la technique d'escalade, la preuve terrain qu'un signal à
gain < 1 module durablement et l'antériorité de l'émulation de registres
viennent de
[PVi1/esphome-twc-control](https://github.com/PVi1/esphome-twc-control) ;
le bloc d'identité Neurio vient du gist public de LucaTNT. Ce projet
n'est ni affilié à, ni approuvé, ni sponsorisé par Tesla, Inc.*


### Validation en boucle fermée de la variante B (17/08, 22:56-23:15, MESURÉ)

Avec la loi à traînée décroissante active (traînée 2,0 A, décroissance
0,15 A/s), dans les conditions exactes qui avaient produit le cycle
limite de ±2,5 A : pompe de piscine + électrolyseur + une clim, la maison
respirant autour du budget. Résultats : verdict de confiance positif
(descente de 16 à 9,1 A à ~1 A/s dans les secondes suivant l'entrée du
publié en zone de traction), puis **11 minutes clouées à l'équilibre
exact (9,1 A) avec zéro oscillation** pendant que la maison descendait et
remontait, zéro cycle contacteur, et une sortie propre (de 9,1 à 15,7 A
en ~6 s une fois la contrainte retombée). La seule alerte émise était un
faux positif du détecteur (seuil posé dans la bande morte ; recalibré à
L+0,85). Trace brute :
`data/traces/2026-08-17_2256_variantB_closed_loop.log`.
