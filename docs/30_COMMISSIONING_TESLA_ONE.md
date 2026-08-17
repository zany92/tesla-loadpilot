# Tesla LoadPilot - commissioning Tesla One, le pas-à-pas vécu

> Sans cette étape, la borne LIT le compteur émulé mais N'AGIT PAS : le
> firmware peut publier des mesures parfaites, tant que le compteur n'est pas
> déclaré et les limites posées dans le menu installateur, aucun bridage
> n'aura lieu (vécu : chaîne complète validée côté RS485, dépassements réels
> à 110 % sans réaction - tout venait de la config Tesla One).

## 0. Prérequis

- Firmware du nœud borne flashé, `TWC Polling Active` = on et
  `TWC Poll Interval` stable (~200 ms) : la borne polle déjà le compteur.
- Application **Tesla One** (application installateur, compte pro non requis
  pour l'accès local) ; connexion au hotspot WiFi de commissioning de la
  borne (procédure standard TWC Gen 3, QR sous la façade).

## 1. Déclarer le compteur

Menu installateur → *Home Load Management* (gestion dynamique) → ajouter un
compteur : la borne détecte le **Neurio** émulé sur son bus RS485 (le bloc
d'identité registres 1-55 + la poignée de main « Generac » 40002-40007
suffisent - c'est exactement ce que vérifie la borne).

## 2. Configurer les CT

| CT | Réglage | Pourquoi |
|---|---|---|
| CT 1 | **Conductor** (phase L1) | mesure de l'arrivée, phase 1 |
| CT 2 | **Conductor** (phase L2) | phase 2 |
| CT 3 | **Conductor** (phase L3) | phase 3 |
| CT 4 | **None** | non câblé dans l'émulation (registres publiés à 0) |

En monophasé : CT 1 = Conductor, CT 2/3/4 = None (le firmware publie déjà
0 sur les phases absentes).

## 3. Poser les limites - l'ordre compte

- **Max Conductor Limit** = LE seuil de régulation : le courant maximal
  autorisé sur chaque conducteur mesuré. La borne calcule en continu
  `marge = Max Conductor Limit − mesure publiée` et bride le véhicule dans
  cette marge. Pour un contrat 15 kVA triphasé : 5 000 VA / 230 V ≈ **21 A**.
- **⚠️ Piège de plancher** : le champ Max Conductor Limit refuse toute
  valeur **inférieure au « Max Output Current »** de la borne (le réglage
  statique de sortie). Si la borne est configurée à 32 A de sortie, le
  Conductor Limit ne descend pas sous 32 → **baisser d'abord Max Output
  Current** (ex. 16 A), puis poser le Conductor Limit voulu (21 A).
- **Piège vécu n°1** : Conductor Limit resté à 32 A sur un contrat 21 A
  = « jamais de bridage » - tous les dépassements passaient sans réaction.
  Les premiers verdicts « le DPM ne marche pas » venaient de là (et des
  capteurs cloud périmés, voir §5).
- Le firmware du nœud borne doit connaître la même valeur : reporter la
  limite Home Load Management dans la substitution `twc_breaker_limit_a`,
  et le disjoncteur de branchement dans `main_breaker_limit_a` (le
  fail-safe publie cette valeur pour bloquer la charge).

## 4. Vérifier que le DPM AGIT

1. Lancer une charge, créer un dépassement contrôlé (bouilloire, four…).
2. Observer les **vitals locaux** de la borne : `http://<IP_BORNE>/api/1/vitals`
   (échantillonner à 2-5 s). Attendu : dès que le CT max franchit la
   limite, la borne réduit/coupe le véhicule en **≤ 5 s**.
3. Signature du DPM actif (mesurée, firmware 26.18) : cycles
   16→0 A à ~1 A/s, remontée ~0,65 A/s, `evse_state` 11→7 à l'arrêt,
   période ~55 s si la contrainte persiste (voir `40_LOI_DE_COMMANDE.md`).

## 5. Pièges de diagnostic rencontrés

- **Ne JAMAIS juger la charge sur les capteurs cloud du véhicule** (API
  Fleet, poll ~10 min, se figent quand la voiture s'endort) : ils ont fait
  conclure DEUX FOIS à tort « DPM inactif » pendant que les vitals locaux
  montraient 4 cycles de bridage en 4 minutes. Source de vérité = vitals
  locaux ou intégration HA `tesla_wall_connector`.
- **`config_status` (vitals) reste non documenté** (valeur 5 observée
  pendant la phase de doute) - ne pas s'en servir comme critère.
- Dans les vitals, `currentA/B/C_a` = courants du **câble véhicule**, PAS le
  compteur reçu (piège d'interprétation vécu deux fois) ; le compteur émulé
  relu par la borne apparaît dans les champs *grid* / Neurio.
- Après modification de la config compteur, un **redémarrage de la borne**
  (disjoncteur) est un réflexe sain avant de conclure quoi que ce soit.
- La borne mémorise la config compteur : une erreur de saisie initiale
  (mauvais type de CT) se corrige en repassant par le menu installateur,
  pas en retouchant le firmware.
