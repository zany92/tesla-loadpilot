# Tesla LoadPilot - loi de commande du DPM TWC Gen 3, comportement MESURÉ

> **C'est la valeur du projet.** Rien de ce qui suit n'est documenté par
> Tesla : tout a été mesuré en conditions réelles (firmware borne **26.18**,
> installation triphasée 15 kVA, limite Conductor 21 A, mesures Linky ~1 Hz,
> vitals borne échantillonnés 2-8 s, plusieurs centaines d'échantillons,
> **57 coupures ré-analysées au recorder** les 13-17/08). Ces constantes
> sont des propriétés du firmware borne + véhicule : **à recalibrer si le
> firmware TWC évolue.**
>
> Version du 17/08 - **modèle définitif** après ré-analyse exhaustive
> (trancheur interne : recorder 13→17/08 ; trancheur externe : PVi1,
> fils communautaires, doc Tesla) et **validation en réel du bloc
> memoryless PVi1-grade** (test 17/08 11:21-11:35, §7). Chaque énoncé est
> marqué **MESURÉ** (nos données), **INFÉRÉ** (déduit, non testé
> directement) ou **RAPPORTÉ** (source externe).

## 1. SERVICE (modulation du pilote) : fonctionnelle SYMÉTRIQUE des 3 voies

La boucle de service - celle qui module doucement le courant offert au
véhicule - ne regarde **PAS la pire voie** publiée :

- **MESURÉ** : ≥ 20 coupures discriminantes (publication par-phase
  différenciée, max > 21 A, moyenne < 21 A) sans **aucune** modulation de
  service préalable - le véhicule reste strictement immobile jusqu'à la
  coupure de protection. ~6 min cumulées de `max > 21` avec `moy < 21`
  sur les épisodes 13-14/08, voiture plate (ex. 13/08 18:52 : 3 min à
  8,1 A constant avec une voie publiée ≈ 22 A en continu). Un service
  par-phase même lent (1-2 A/min) aurait produit une dérive visible :
  absente partout.
- **MESURÉ** : l'engagement du service n'a été observé **que lorsque la
  moyenne des 3 voies publiées franchit la limite** (épisode ACTIF-MAX
  17/08 00:36-00:42 : aucune réaction à moy 20,6-20,9 malgré des max
  21,3-22,4 ; modulation dès moy ≥ 21,3 ; récupération dès moy < 20).
- **Ambiguïté résiduelle (non tranchée)** : moyenne vs min-des-publiés.
  Tous nos épisodes différenciés ont min ET moy < 21 simultanément ; en
  publication symétrique les trois grandeurs coïncident. **Sans incidence
  en publication symétrique** (toute fonctionnelle symétrique s'engage au
  même point). Le test académique fermant (2 voies ~22 / 1 voie ~18 sous
  clamp) est décrit dans le verdict du trancheur, jamais exécuté.
- **RAPPORTÉ (convergent, multi-sources fw 26.x)** : la dynamique de
  service loin de la limite est **LENTE, en minutes** - une « trajectoire »
  incrémentale autour de la limite configurée, pas un asservissement
  `setpoint = f(CT)` (fil HA Community : hausse suivie/baisse ignorée,
  pilotage à ±0,1 A de la fuse, descentes en minutes même à zéro dispo -
  d'où l'escalade PVi1 « +0,1 au-dessus de la limite » pour forcer un
  arrêt). PVi1 lui-même documente « ramps down very slowly (minutes) ».
- **MESURÉ** : près de la limite, la réaction est courte : ~5-20 s entre
  le franchissement de la moyenne et le premier mouvement du pilote
  (19 s au clamp du test 17/08 ; dizaines de secondes en ACTIF-MAX).
- **MESURÉ (17/08)** : pas d'incréments fins ~1 A côté borne en descente ;
  la **remontée** après retour de marge franche est autonome et cadencée
  **~1 A / 30 s** (11→16 A en ~2 min, §7).
- **RAPPORTÉ (externe, important)** : personne - PVi1 compris - n'a
  démontré la loi de service exacte. Le « min par phase » de PVi1 est une
  inférence auto-rapportée sur 1-2 épisodes vécus (« not officially
  confirmed by Tesla, just inferred from testing »), sans logs bruts
  publiés ; comme équilibre long terme il reste mieux supporté que la
  moyenne dans SES données, mais nos épisodes courts (43 s à 3 min)
  l'excluent comme loi rapide. Tension d'échelle de temps non résolue -
  encore une raison de publier symétrique.

## 2. PROTECTION : PIRE PHASE, morsure puis coupure intégrale

Indépendante du service, la protection est calée sur le **CT maximum** -
`max(CT1, CT2, CT3)` comparé à la Max Conductor Limit (21 A ici) :

- **Morsure** (MESURÉ) : grignotage **2-6 A** du pilote, déclenché à
  max ≈ **21,3** (jusqu'à ~23), latence **≤ 5 s**, durée 5-10 s, avec
  **récupération complète** dès que l'excès instantané cesse - y compris
  pendant que la voie fautive reste > 21 (sonde A : récupération à 15,2 A
  en 8 s avec L3 toujours à 21,3-21,9). Une morsure récupère ; un service
  tient son palier : c'est le critère de distinction.
- **Coupure** (MESURÉ, très haute confiance) : ouverture du contacteur
  quand l'**intégrale d'excès pire-phase** atteint **~20-21 A·s**
  (mesuré ≈ 21 A·s à la sonde A ; théorie ~20), avec **décroissance de
  l'intégrale quand la voie repasse sous la limite** - ce qui explique
  les longues expositions tolérées à faible excès (55 s tolérées à ~21,8
  observées historiquement). ≥ 20 coupures avec moy < 21 (jusqu'à moy
  11-16) et **zéro contre-exemple** exigeant moy ≥ 21 : la protection ne
  moyenne jamais.
- Durée max > 21 la plus courte menant à coupure à la sonde A : **43 s**
  (L3 franchit 21 à 00:14:50, coupure 00:15:33 - et non « 2 min 30 »,
  qui était la fenêtre d'observation entière).

## 3. PLAUSIBILITÉ : corrélation 1:1, jamais de dilution

Le firmware 26.18 vérifie que le signal compteur est corrélé à sa propre
sortie : quand la voiture charge, le courant publié doit **monter
d'autant**.

- **RAPPORTÉ (PVi1, mesuré chez lui)** : diluer la composante voiture
  (moyenne des phases, lissage EMA du publié) casse la corrélation → arrêt
  en secondes. Un gain multiplicatif sans retard est accepté ; un retard
  temporel est rejeté.
- **MESURÉ (cohérent)** : toutes nos publications où le courant propre de
  la borne remontait 1:1 (RAW, puis pire-phase-symétrique où `m_p` inclut
  la voiture) ont été acceptées sans code d'erreur de plausibilité ; les
  yoyos observés en ACTIF-MAX v1 s'expliquent entièrement par notre
  estimateur (fantôme Linky-en-retard), pas par un rejet borne.
- Règle de conception : **le signal publié doit suivre le courant voiture
  1:1 - jamais de dilution, jamais de retard sur cette composante.**

## 4. SESSION : la mémoire du véhicule et l'abandon silencieux

Comportements côté Tesla (véhicule), mesurés à travers la borne :

- **Ampères mémorisés PAR LIEU** (MESURÉ) : à chaque redémarrage de
  session, le véhicule ré-applique sa consigne mémorisée pour le lieu
  (souvent 16 A), écrasant tout réglage fait pendant la session
  précédente. Un réglage posé PENDANT une charge stable, lui, tient.
- **Abandon après ~3 sessions perturbées** (MESURÉ 2× le 17/08) : après
  environ trois démarrages de charge interrompus en quelques minutes, le
  véhicule **cesse de retenter**. Signature exacte : `evse_state` → **9**,
  **zéro alerte côté borne**, **compteur « cycles-en-charge » figé** (le
  contacteur ne s'était pas refermé en charge) - rien ne distingue cet
  abandon d'une fin de charge côté borne. **Relance via l'application
  requise** (ou débranchement/rebranchement). Toute architecture à pauses
  répétées doit le prévoir : relance automatique post-relâche si API
  disponible, sinon notification explicite, et anti-cyclage pour ne
  jamais y arriver.

## 5. Dynamiques mesurées (constantes de calibration)

| Grandeur | Valeur mesurée |
|---|---|
| Morsure : latence après excès pire-phase | ≤ 5 s |
| Morsure : amplitude / durée | 2-6 A / 5-10 s, récupération complète |
| Coupure : intégrale d'excès pire-phase | ~20-21 A·s (décroissante sous la limite) |
| Service : latence près de la limite (moyenne ≥ 21) | ~5-20 s |
| Service : remontée autonome à marge franche | ~1 A / 30 s |
| Service : dynamique loin de la limite | minutes (RAPPORTÉ, convergent) |
| Descente en coupure | ~1 A/s |
| Remontée après réautorisation | ~0,65 A/s |
| Fenêtre contacteur ouvert dans un cycle | ~15-20 s |
| Période du bang-bang entretenu (publication RAW gain 1) | ~55 s |
| Minimum véhicule (Tesla, AC tri) | ~6 A |
| `evse_state` pendant l'arrêt d'un cycle / abandon véhicule | 11 → 7 / 11 → 9 |
| Effet d'un ampère de charge (tri) | ~230 VA par phase et par ampère |
| Cadence de poll Modbus du compteur | ~190-200 ms |
| Timeout de relance Modbus (deadline de réponse) | ~66 ms |
| Temps de réponse consigne J1772 côté véhicule | ~5 s |

## 6. CONSÉQUENCE D'ARCHITECTURE : la publication pire-phase symétrique clampée

C'est le point d'arrivée du projet (bloc « PVi1-GRADE (17/08) » de
`kc868-a6-1.yaml`), et il découle mécaniquement des §1-§3 :

```
dispo_p  = budget − biais − mesure_p        (par phase, clampé [0 ; L])
publie_p = L − min(dispo_1, dispo_2, dispo_3)     (identique sur les 3 voies)
```

- **Service symétrique + protection pire-phase + loi de service exacte
  inconnue ⇒ publier la PIRE PHASE À L'IDENTIQUE sur les 3 voies** est la
  seule publication robuste : min = moy = max par construction, donc la
  boucle de service s'engage exactement à la vraie contrainte **quelle que
  soit la fonctionnelle réelle** (moyenne, min-des-publiés ou autre).
- **Trip impossible par construction** : le publié est clampé ≤ L (21 A) -
  la protection pire-phase ne voit jamais d'excès, morsures et coupures
  disparaissent. Un échec de ce bloc est un non-démarrage ou un hunting
  mou, jamais un claquement de contacteur.
- **Escalade volontaire** : la borne rampant en minutes vers « zéro
  dispo » (§1) et pouvant garder un résiduel indéfiniment, après **120 s
  à dispo nulle** le bloc publie **L + 0,1** sur les 3 voies pour forcer
  un arrêt franc (technique PVi1, RAPPORTÉ puis MESURÉ chez nous).
- **Aucun estimateur voiture** : la mesure publiée INCLUT le courant de la
  borne → le publié suit la voiture 1:1, la plausibilité (§3) est
  satisfaite par construction. Aucun état interne hors le timer
  d'escalade (voir leçon 28 de `contrat_electrique_LOGIQUE.md` et
  l'épilogue de `60_ETUDE_SYNTHETISEUR.md` : chaque état interne ajouté
  avait créé son propre bug).
- Buffer de sécurité : la ressource offerte est `budget = Enedis × (1−b)`
  (b = 10 % par défaut) - la voiture n'exploite jamais 100 % de la marge,
  en régime établi comme en transitoire.

## 7. VALIDATION du 17/08 (11:21-11:35, trace 3 s, bloc PVi1-grade ACTIF)

Baseline `contactor_cycles` = 470. Voiture 16 A, maison vivante (clim,
pompe piscine). **MESURÉ** :

| Heure | Événement | Publié (sym.) | Voiture |
|---|---|---|---|
| 11:21-11:23 | régime établi | 18,1-18,3 | 16,0-16,1 stable |
| 11:23:42 | démarrage clim → **clamp à 21,0 pile** | 21,0 | 16,0 |
| 11:24:01 | 1re modulation douce (**19 s** après le clamp) | 20,3 | 16,0 → **15,1** |
| 11:26:03 | palier suivant (publié ~20,1 soutenu) | 20,1 | → **13,1** |
| 11:27:48-11:28:03 | pompe piscine (publié 20,8-20,9) | 20,9 | → **11,1** |
| 11:28-11:30 | **palier 11,1 TENU ~2 min, zéro chasse** | ~19,1 | 11,1 |
| 11:29:34-11:30:00 | fin de charge maison, publié chute 15,4 → 13,6 | 13,6 | 11,1 |
| 11:30:03 → 11:32:03 | **remontée autonome ~1 A / 30 s** | 13,6 → 18,4 | 12,1 → 13,1 → 14,1 → 15,1 → **16,1** |
| 11:32-11:35 | régime établi retrouvé | 18,1-18,4 | ~16,0 |

Bilan : `contactor_cycles` = **470 constant** (zéro coupure), **zéro
morsure**, `evse_state` = 11 en continu, modulation douce descendante ET
remontée autonome - **la borne 26.18 SAIT tenir un palier sous la demande
du véhicule** quand le signal publié est borné ≤ limite. Deux échelons de
charge réels absorbés sans aucun événement.

## 8. Corrections d'épisodes et verdicts antérieurs re-scopés

À lire si l'on compare avec les versions antérieures de ce document ou
avec les notes de mission :

1. **« Plafond du firmware » (verdict du 14/08) - RE-SCOPÉ.** Le constat
   « la borne ne tient jamais un palier sous la demande ; états stables =
   pleine demande ou arrêt franc ; période ~55 s » reste vrai - **mais
   uniquement en publication RAW auto-référente (gain de boucle 1)**, où
   chaque ampère pris par la voiture remonte intégralement dans la mesure
   publiée. Ce n'était pas un plafond du firmware : c'était la signature
   du gain de boucle. Avec la publication pire-phase symétrique clampée
   (§6), les paliers sous consigne existent et tiennent (§7). Les mesures
   de latence restent valables telles quelles : l'erreur transitoire vaut
   `rampe_véhicule × latence_mesure`, et au-delà de ~1 Hz la fraîcheur de
   la mesure n'apporte plus rien (le ~0,46 s testé n'avait rien changé au
   comportement RAW) - les pinces sub-seconde restent inutiles.
2. **Escalier « sonde A » du 17/08 00:09-00:12 (15→14→12→13→14→15) -
   RÉ-ATTRIBUÉ.** Ce n'était pas la borne : c'est le contrôleur **Fleet
   cloud** (mode limite) - `number.whale_courant_de_recharge` change 2-5 s
   avant chaque mouvement voiture, et la remontée 1 A/30 s est la
   signature du réglage Fleet du 14/08. La sonde propre commence à
   00:13:21 (borne_seul + manuel, zéro commande Fleet ensuite).
3. **« Épisode 16/08 15:39-15:41 » - N'EXISTE PAS.** Aucune session de
   charge au recorder entre le 14/08 17:07 et le 16/08 19:03. L'épisode
   décrit (clim + réduction 13→10) est le **14/08 15:38-15:42** : 100 %
   commandes Fleet cloud (13 → 10 → 6 suivies par la voiture), borne
   passive (max publié 18,1 < 21), non-discriminant.
4. **Durée d'excès de la sonde A : 43 s**, pas 2 min 30 (§2).
5. **Les « deux morsures furtives » de la sonde A** étaient bien de la
   protection pire-phase (récupération sous excès persistant), pas un
   service par-phase timide (§2).

## 9. Chronologies de preuve historiques (résumées, toujours valables)

**A. Le DPM agit, et vite (13/08 après-midi, phase 3 à 107 %).** Cloud
véhicule figé ; les vitals locaux montrent la borne cycler le véhicule
16→0→16 A quatre fois en 4 min, réaction ≤ 5 s après franchissement -
relu au recorder le 17/08 : pk_max 23-24 / moy 18,3-18,7, épisode
discriminant protection = pire phase. Leçon : « ne JAMAIS diagnostiquer
la charge sur l'API cloud - toujours les vitals locaux ».

**B. Couper les équipements ne sert à rien pendant une charge (13/08
soir, invité 16 A).** Le DPM redistribuait immédiatement au véhicule
chaque watt libéré par le délestage (4 clims coupées) - bang-bang
16→0→16 pendant ~9 min. Leçon : **réguler la voiture D'ABORD.**

**C. Le palier proportionnel est un mirage EN RAW (test dédié, 10
cycles).** Biais laissant ~14 A face à une demande de 16 A : rampe →
dépassement → coupure → redémarrage avec ré-application des 16 A
mémorisés par lieu →…, période ~55 s. C'est ce constat que le §8.1
re-scope : vrai à gain de boucle 1, levé par la publication clampée.

**D. Même à 3 s de latence, la rampe du véhicule rebondit.** La borne
soustrait son courant instantané d'une mesure datée : erreur transitoire
= rampe × latence, indépendamment de la qualité de la mesure.

**E. La fenêtre « code 10 » (biais rampé).** Cible de biais élevée + rampe
de descente 0,5 A/5 s = 160 s de refus de démarrage (« puissance
disponible insuffisante ») sans aucune charge. Correctif : application
immédiate de la cible quand le contacteur est ouvert + capteur « biais
appliqué ».

Journée noire de référence : +58 alertes borne / 29 cycles contacteur en
une journée (échelons de biais pendant les rampes) - d'où la rampe de
biais côté firmware (montée 1 A/5 s, descente 0,5 A/5 s).

Plafonds amont : Linky ~1 Hz interne, TIC 9600 bd (limites Enedis). Les
pinces dédiées (Shelly Pro 3EM…) ne se justifient que comme source de
mesure là où le compteur national est inéligible
(`15_FOURNISSEURS_MESURE.md`) - jamais pour « améliorer » la modulation.

## 10. Architecture de contrôle qui en découle

- **Publication pire-phase symétrique clampée (§6) = le régulateur borne**
  - modulation douce continue, trip impossible, aucun état interne ;
- **consigne API véhicule (Fleet aujourd'hui, BLE à l'étude) = la
  modulation fine contractuelle** pour le véhicule propriétaire - le seul
  canal documenté et stable à travers les firmwares ;
- **le biais borne reste le levier universel** (invités, tout véhicule,
  sans cloud) - exploité en tout-ou-rien avec rampe, plus l'escalade
  L + 0,1 pour les arrêts francs ;
- le DPM natif de la borne (morsure/coupure) n'est plus qu'un **filet
  qu'on ne sollicite jamais** : le clamp l'empêche de voir un excès.
