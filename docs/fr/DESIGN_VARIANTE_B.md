# DESIGN - Variante B : casser le yo-yo par asymétrie de relâche (traînée)

> **Statut : DESIGN, rien n'est flashé.** Prépare le flash n° 3 du nœud
> `kc868-a6-1` (ESPHome 2026.7.4). Complète - sans le remplacer - le bloc
> « PVi1-GRADE v2 co-variant » (`/config/esphome/kc868-a6-1.yaml`,
> lambda `recompute_ct`, bloc l. ~1476-1569) issu de
> `DESIGN_LOI_COVARIANTE.md` (variante A, flashée et validée le 17/08
> soir 19:06-19:43).
>
> Sources : leçons 28-31 (`/config/docs/contrat_electrique_LOGIQUE.md`),
> `BEHAVIOR.md` §4 (défiance) et §8 (validation du soir),
> `40_LOI_DE_COMMANDE.md` §1-§5 (dynamiques mesurées), traces du 17/08
> soir (`test_soir_v3.log`, `test_v2_toutes_clims.log`,
> `test_loi_douce.log`) + historique recorder 20:20-20:25.
> Aucun secret ici.

## 0. Recommandation ferme (résumé exécutif)

**Retenir le candidat (b) sous sa forme « traînée additive
décroissante »** : la loi v2 reste STRICTEMENT inchangée en contrainte
(leçon 31 : le gain sur la composante voiture est intouchable) ; en
**sortie** de contrainte, le publié ne replonge plus instantanément sous
L mais décroît vers la réalité à vitesse bornée (~0,15 A/s, ≤ 13 s),
via **un seul état ajouté** (un timestamp, patron identique à
`capped_since_ms`). C'est le seul des trois candidats qui attaque la
cause racine du yo-yo (la remontée immédiate de la borne dès publié < L)
sans diluer l'écho voiture ni recréer une valeur morte. Il a un
**précédent d'acceptation déjà mesuré chez nous** : la rampe de biais
(0,1-0,2 A/s) est exactement le même objet vu de la borne - un offset
additif qui dérive lentement - et elle est absorbée sans broncher depuis
le lot 13. Kill-switch sans re-flash : number « TWC loi trainee » à 0.

Le candidat (a) - nudge alterné olaliv - ne supprime pas le yo-yo (il
continue de montrer publié < L un cycle sur deux dès la sortie de
contrainte) et double l'exposition intégrale en contrainte : conservé
uniquement comme repli si la borne rejetait la traînée (improbable, cf.
précédent biais). Le candidat (c) - équilibre décalé sous le budget -
est rejeté : il recrée le régime « valeur quasi statique » de la
leçon 29 à l'équilibre contraint (qui peut durer des heures), ou dilue
dans la bande (leçon 31), et ne réduit pas l'amplitude du cycle, qui est
une propriété de la boucle, pas du centrage.

## 1. Le problème mesuré : anatomie du yo-yo (17/08, 20:20-20:25)

Conditions : maison ~10 A sur la pire phase, budget 19,53 A
(b = 10 %) → équilibre voiture ≈ 9,5 A. Loi v2 (gain 0,5 /
emax 1,0), ACTIF-MAX. Cycle limite mesuré ±2,5 A, période ~20 s,
**7 excursions publié > 21 en 5 min → coupure intégrale (~20 A·s) à
20:25:37**.

Les quatre temps du cycle :

1. **Montée** : la voiture est sous son équilibre → e < 0 → publié =
   o_raw < 21 → la borne relâche et fait remonter la voiture (près de
   la limite, la remontée est rapide - récupération type post-morsure,
   PAS la remontée lente 1 A/30 s de marge franche) ;
2. **Bascule** : la voiture dépasse l'équilibre → e > 0 → le publié
   SAUTE : avec gain 0,5 et un excès vite ≥ 2 A, `L + clamp(0,5·e,
   0,1, 1,0)` sature → publié 21,95-22,05 (dither compris) ;
3. **Plongée** : 21,95+ est AU-DELÀ du seuil d'action réel de la borne
   (~21,9, §2) → descente forte ~1 A/s → la voiture SOUS-dépasse
   l'équilibre de ~2,5 A ;
4. **Rebond** : e < 0 → publié retombe D'UN COUP sous 21 (jusqu'à
   ~18,5) → la borne lit « marge franche revenue » → remontée → retour
   au temps 1.

**La racine est la SYMÉTRIE de la publication** : la loi v2 est une
fonction instantanée de la réalité, donc le publié franchit L vers le
bas aussi brutalement qu'il l'a franchi vers le haut. Chaque excursion
charge l'intégrale de protection (~3 A·s/excursion) plus vite que la
décroissance sous la limite ne la vide → coupure au bout de 7 cycles.
À noter : **aucune défiance pendant tout l'épisode** - la plausibilité
v2 fonctionne ; c'est la protection qui a coupé. Le problème à
résoudre est dynamique, pas un problème de confiance.

## 2. Données fraîches qui contraignent le design (17/08 soir)

- **Leçon 31 - l'adoucissement est interdit** : gain 0,25 / emax 0,5 =
  dilution 4:1 en contrainte → la rampe de reprise de la voiture a été
  partiellement absorbée → **re-défiance latchée**. La règle
  never-dilute de PVi1 fixe un plancher ~0,5 au gain effectif sur la
  composante voiture. Conséquence de design : **la branche e > 0 de la
  v2 ne doit pas être touchée** ; toute correction doit vivre hors
  contrainte ou à la frontière.
- **Bande morte de la borne mesurée** (`test_loi_douce.log`,
  20:31-20:35) : ~110 s à publié 21,45-21,55 puis ~95 s à 21,75-21,85,
  voiture rigoureusement immobile à 12,0-12,1 A - la borne ne tire
  franchement qu'à **~21,9+**. La micro-loi rapportée « L+0,1 →
  −1 A/s » n'est PAS vérifiée sur notre 26.18 en deçà de ~+0,9.
- **Intégrale tolérante à faible excès** : ~35 A·s encaissés à +0,5
  sans coupure (et 70 s+ à +0,45-0,55 sans réaction) - la décroissance
  sous la limite et/ou un seuil d'armement rendent les bornes du §4.1
  du design v2 très pessimistes à faible excès. En revanche à ~+1
  (21,95-22,05 soutenu par salves), la coupure est bien survenue à
  ~20 A·s cumulés.
- Relecture utile : la borne a en fait TROIS régimes autour de L -
  **remonte** (publié < 21), **tient** (21 ≤ publié ≲ 21,9),
  **plonge** (≳ 21,9). Le yo-yo v2 saute directement du régime
  « remonte » au régime « plonge » et retour, sans jamais exploiter la
  zone « tient ». Le design gagnant doit faire ATTERRIR le publié dans
  la zone « tient » après chaque excursion, au lieu de le laisser
  retomber en zone « remonte ».

## 3. Candidats

### 3.a - Nudge alterné (olaliv 1 s / 1 s)

Cycle pair = réalité corrélée brute (clampée à L+1 - le clamp est
OBLIGATOIRE : sans lui, un o_raw à L+2,5 publié un cycle sur deux
injecte ~1,25 A·s par seconde → coupure en ~15-25 s de contrainte) ;
cycle impair = L + nudge directionnel borné ±1 (signe de e).

- **Plausibilité** : excellente sur le papier - pente 1 la moitié du
  temps, précédent mesuré gagnant chez olaliv (mais en MONO 26.2 ;
  jamais testé en tri 26.18). À notre cadence de poll ~190 ms, chaque
  valeur d'une seconde est vue ~5 fois : la borne voit un carré
  0,5 Hz d'amplitude jusqu'à ~2 A - un compteur réel ne fait jamais
  ça ; risque non nul de défiance d'un genre nouveau.
- **Yo-yo** : NON résolu. Hors contrainte (temps 4 du cycle), le cycle
  pair publie o_raw < L un cycle sur deux → la borne voit la marge
  revenue à 0,5 Hz → la remontée persiste (au mieux ralentie ~×2). Le
  candidat traite la fidélité d'écho - qui n'est PAS le problème de ce
  soir (zéro défiance) - pas la symétrie.
- **Intégrale** : en contrainte, duty ~50 % à L+1 (les deux types de
  cycles y convergent) ≈ 0,5 A·s/s → vie ~40-70 s avec la tolérance
  mesurée : PIRE que v2.
- **États ajoutés** : zéro (parité horloge).
- **Démarrage / biais / pause** : comme v2 (o_raw vrai un cycle sur
  deux ; pause → les deux cycles ≈ L+1 → arrêt service).

Verdict : **repli plausibilité uniquement** (si la borne rejetait la
traînée du candidat b), pas une réponse au yo-yo.

### 3.b - Hystérésis directionnelle (retenir la redescente sous L)

Deux formulations, dont une seulement est conforme :

**b1 - plancher tenu (REJETÉE).** À la sortie de contrainte, tenir le
publié à ≥ L−ε pendant 10-20 s (ou jusqu'à e < −marge). Analyse
plausibilité : pendant la tenue, le publié ne suit plus la réalité à la
baisse. Les chutes MAISON non suivies passent (mesuré : le pare-feu
anti-glitch retient déjà les chutes > 5 A sur 2 échantillons, et
aucune des deux entrées en défiance mesurées n'implique la corrélation
à la baisse - elles sont « valeur sous le courant propre » et « rampe
voiture MONTANTE absorbée »). MAIS : pendant la tenue, si la borne
relâche et que la voiture REMONTE, o_raw remonte VERS le plancher sans
que le publié bouge → jusqu'à ~2,5 A de rampe voiture montante
absorbée pendant 10-20 s → **c'est le chemin d'entrée n° 2 de la
défiance, à l'identique de la leçon 31**. Le critère « jamais de
dilution de la composante voiture pendant SES rampes » est violé dans
la direction exactement dangereuse. Rejet.

**b2 - traînée additive décroissante (RETENUE).** Reformulation qui
préserve la pente 1 partout : à la sortie de contrainte, le publié
vaut `min(o_raw + r(t), L)` où `r(t)` est un offset qui décroît
linéairement de R0 (2,0 A) à 0 en ~13 s (0,15 A/s). Les DELTAS de la
réalité passent intégralement (`Δpub = Δo_raw − 0,15/s` dès que le
min ne mord plus) : une rampe voiture, montante ou descendante, est
échoyée 1:1 instantanément, seulement superposée à une dérive
descendante constante et lente - physiquement identique à une clim qui
s'éteint, et **identique en nature et en amplitude à la rampe de biais
(0,1-0,2 A/s) que la borne absorbe sans broncher depuis le lot 13**.
Le `min(·, L)` borne le publié à L pendant les ~2 premières secondes
(o_raw plonge à ~1 A/s, la traînée ne retient que 0,15 A/s : le cap ne
mord que très brièvement) : la borne lit « tient », pas « excès », et
jamais un excès fabriqué hors contrainte.

Effet sur le cycle : au temps 4 (rebond), au lieu de retomber d'un coup
à ~18,5, le publié atterrit à L pile, puis glisse vers la zone
« tient » et n'entre en zone « remonte » que lentement et d'une
profondeur vue réduite de r(t) (2,5 A réels → ~0,9 A vus à t = 2,5 s).
La remontée repart tard, doucement, et depuis l'équilibre - plus
depuis un creux de −2,5 A.

- **Plausibilité** : conforme au plancher - gain 1 sur la composante
  voiture dans les deux sens, aucun retard (l'offset ne dépend pas des
  entrées passées, seulement de l'instant d'armement), branche
  contrainte inchangée. Précédent d'acceptation : rampe de biais.
- **Intégrale** : la traînée n'ajoute d'excès que via le cap à L
  (~0 A·s, publié = L n'est pas un excès) ; les excursions restent
  celles de la v2 mais leur CADENCE chute (période estimée ≥ 60-90 s
  contre ~20 s) → l'intégrale décroît entre deux excursions au lieu de
  s'empiler. Marge confortable vs la tolérance mesurée (35 A·s à
  +0,5).
- **Amplitude/période résiduelles attendues** : première excursion d'un
  échelon de charge inchangée (elle est pilotée par la maison) ;
  ensuite cycle résiduel estimé ±0,5-1 A autour de l'équilibre,
  publié résident surtout dans [20,5 ; 21,6], excursions > 21,9
  seulement sur vrais échelons.
- **États ajoutés** : **UN** - `tail_since_ms` (timestamp, patron
  identique à `capped_since_ms` ; R0 et la pente sont des constantes).
  Modes de défaillance du nouvel état : il ne peut pas rester coincé
  (décroissance calculée sur `millis()`, pas par tick - donc
  insensible à la cadence événementielle de `recompute_ct` - et
  purgée à zéro dès expiration, contacteur ouvert, fail-safe, ou
  number à 0).
- **Démarrages de session** (référence ≤ L−5 = 16) : la traînée élève
  le publié ≤ 13 s après chaque épisode… mais **tout démarrage se fait
  contacteur OUVERT, et contacteur ouvert purge la traînée** → aucun
  démarrage n'est jamais retardé par la traînée. La reprise autonome
  post-pause mesurée « à la seconde de la relâche » (BEHAVIOR §8) est
  préservée par la même purge (la relâche du biais se fait contacteur
  ouvert).
- **Biais / pause** : biais 16 → o_raw ≫ L → branche contrainte
  inchangée (publié L+emax, arrêt service ~1 A/s). À la relâche :
  contacteur ouvert → traînée purgée → comportement v2 exact.

### 3.c - Bande morte asymétrique (équilibre décalé sous le budget)

Viser un équilibre à budget − 0,5 pour que les oscillations naturelles
ne traversent plus L. Deux implémentations, toutes deux fautives :

- **Décaler le budget** (b % de 10 → ~12,5) ne décale RIEN : la boucle
  fermée se recentre d'elle-même là où le publié oscille autour de L -
  l'équilibre est DÉFINI par le franchissement. On perd 0,5 A de
  charge, le cycle continue de traverser L. (L'amplitude ±2,5 A est
  une propriété du gain de boucle et des latences, pas du centrage.)
- **Aplatir la publication dans la bande e ∈ (−0,5 ; 0]** (publier L,
  ou L + 0,1·e) : la borne « tient » dans la bande → l'équilibre se
  pose dedans → le publié devient **quasi statique à ~21,0 pour toute
  la durée de l'équilibre contraint - potentiellement des heures**.
  C'est la reconstitution exacte du régime leçon 29 (valeur saturée
  constante → défiance), que le dither ±0,05 n'a PAS suffi à éviter
  (mesuré : le dither ne guérit ni ne prévient la défiance,
  BEHAVIOR §4). La version « pente 0,1 » y ajoute une dilution 10:1
  des mouvements dans la bande - dont les rampes voiture qui la
  traversent (leçon 31). Et si la voiture ne module pas dans la bande,
  la maison seule y bouge : ±0,3 A × 0,1 = ±0,03 publié - statique en
  pratique.
- États ajoutés : zéro. C'est sa seule vertu.

Verdict : **rejeté** - il échange un risque dynamique quantifié
(coupure, récupérable) contre un risque de défiance prolongée (le mode
de panne le plus coûteux du système, des heures de cure).

### Tableau comparatif

| | (a) nudge alterné | (b1) plancher tenu | **(b2) traînée additive** | (c) bande asymétrique |
|---|---|---|---|---|
| Tue le yo-yo | non (relâche vue 0,5 Hz) | oui | **oui** | non (recentre sans amortir) |
| Plancher plausibilité (écho voiture 1:1 pendant SES rampes) | oui (½ temps pente 1) | **VIOLÉ** (rampe montante absorbée ≤ 2,5 A / 20 s) | **conforme** (pente 1 + dérive −0,15 A/s, précédent biais) | violé (statique heures ou dilution 10:1) |
| Exposition intégrale | pire que v2 (~0,5 A·s/s en contrainte) | faible | **faible** (cadence d'excursions ÷3-4, cap à L = zéro excès fabriqué) | faible |
| Amplitude / période résiduelles | ~inchangées / ~20 s | ±1 A / > 60 s | **±0,5-1 A / ≥ 60-90 s** | ±2,5 A recentrées |
| États ajoutés (leçon 28) | 0 | 1 | **1** (`tail_since_ms`) | 0 |
| Démarrage session | comme v2 | retardé ≤ 20 s | **jamais retardé** (purge contacteur ouvert) | comme v2 |
| Biais / pause | comme v2 | reprise retardée | **reprise instantanée** (purge) | comme v2 |
| Précédent | olaliv (mono 26.2) | aucun | **rampe de biais acceptée (nous, tri 26.18)** | aucun |

## 4. Spécification retenue - « v2 + traînée » (b2)

### 4.1 Pseudo-code exact (mêmes conventions que le bloc v2)

Seule la branche `e <= 0` du bloc co-variant change, plus une purge
dans la branche « pas de mesure ». La branche `e > 0` est inchangée
au caractère près (leçon 31).

```text
# NOUVEAU global (LE seul état ajouté, patron capped_since_ms) :
#   tail_since_ms : uint32_t, restore_value no, initial 0
# NOUVEAU number (kill-switch sans re-flash) :
#   twc_law_tail  "TWC loi trainee"  A, min 0, max 2.5, step 0.1,
#                 restore_value false, initial 2.0   # 0 = traînée coupée = v2 exact
# NOUVELLE substitution :
#   tail_decay_aps: "0.15"          # pente de décroissance (A/s) - même ordre
#                                   # que la rampe de biais descente (0,1 A/s)

# ---- dans recompute_ct, bloc co-variant, APRÈS le calcul de e ----
float r0 = id(twc_law_tail).state;
if (std::isnan(r0) || r0 < 0.0f || r0 > 2.5f) r0 = 2.0f;   # garde NaN

if (e <= 0.0f) {                                  # HORS CONTRAINTE
  if (id(capped_since_ms) != 0) {                 # FRONT de sortie de contrainte
    id(tail_since_ms) = bnow;                     # armer la traînée
    id(capped_since_ms) = 0;
  }
  const bool ctc_open = id(twc_contactor_seen) && id(twc_contactor_available)
                        && !id(twc_contactor_closed);
  if (ctc_open || r0 <= 0.0f) id(tail_since_ms) = 0;   # purge : démarrages et
                                                       # reprises jamais retardés
  if (id(tail_since_ms) != 0) {
    float r = r0 - ${tail_decay_aps} * (float)(bnow - id(tail_since_ms)) / 1000.0f;
    if (r <= 0.0f) { id(tail_since_ms) = 0; o = o_raw; }
    else           { o = std::min(o_raw + r, L); }     # jamais d'excès fabriqué
  } else {
    o = o_raw;                                    # v2 exact
  }
} else {                                          # EN CONTRAINTE - INCHANGÉ
  float exc = kg * e;
  if (exc < 0.1f) exc = 0.1f;
  if (exc > emax) exc = emax;
  o = L + exc;
  if (id(capped_since_ms) == 0) id(capped_since_ms) = bnow;
  if (bnow - id(capped_since_ms) >= (uint32_t)${escalation_timeout_ms})
    o = std::max(o, L + 0.1f);
}
if (id(twc_charge_stop).state) o = std::max(o, L + 0.1f);   # STOP inchangé
o += dth;                                         # dither inchangé
# ---- dans la branche « else » finale (pas de mesure / control OFF) ----
id(capped_since_ms) = 0;
id(tail_since_ms) = 0;                            # purge fail-safe
```

Points d'implémentation :

- la décroissance est calculée sur `millis()` depuis l'armement, PAS
  par décrément à chaque appel - `recompute_ct` est 1 Hz **plus
  événementiel**, un décrément par appel accélérerait la traînée sur
  les rafales d'événements ;
- ré-entrée en contrainte pendant la traînée : la branche `e > 0`
  reprend naturellement la main (elle ne lit pas `tail_since_ms`) ; à
  la sortie suivante le front ré-arme un timestamp frais ;
- ordre des purges : le test contacteur-ouvert vient APRÈS l'armement
  du front, pour que la purge gagne toujours (une sortie de contrainte
  contacteur ouvert - fin de pause - n'arme jamais de traînée) ;
- `sh_*` reçoivent `o` comme aujourd'hui → la traînée est
  intégralement observable en OMBRE-MAX ;
- le firmware générique `esphome/packages/twc-core.yaml` (dépôt
  tesla-loadpilot) devra recevoir le même bloc + le number
  (« Law Release Tail »), comme pour gain/emax au flash n° 2.

### 4.2 Réglages par défaut et leviers

| Paramètre | Valeur | Rôle | Pourquoi cette valeur |
|---|---|---|---|
| `twc_law_tail` (R0) | 2,0 A (number, 0-2,5) | profondeur de relâche masquée à la sortie | couvre le sous-dépassement mesuré (~2,5 A) au facteur de décroissance près ; 0 = kill-switch live = v2 exact |
| `tail_decay_aps` | 0,15 A/s (substitution) | durée de la traînée (R0/pente ≈ 13 s) | dans la fourchette de la rampe de biais déjà acceptée (0,1-0,2 A/s) ; ≥ 10 s pour couvrir la période du yo-yo, ≤ 20 s pour rester sous la fenêtre contacteur |
| gain / emax | 0,5 / 1,0 - INCHANGÉS | branche contrainte | leçon 31 (plancher never-dilute) ; emax 1,0 nécessaire pour atteindre le seuil d'action réel ~21,9 |
| b % | 10 - INCHANGÉ | budget | le recentrage ne traite pas le yo-yo (§3.c) |

## 5. Ce que l'OMBRE peut valider - et ce qu'elle ne peut PAS

**Le yo-yo est une dynamique en boucle FERMÉE : l'ombre ne boucle
pas.** En OMBRE-MAX, la borne réagit au publié v2, pas à l'ombre ; la
trajectoire de la voiture - donc o_raw - reste celle que la v2
produit. L'ombre ne peut donc PAS démontrer la disparition du cycle
limite, ni mesurer l'amplitude/période résiduelles, ni prouver
l'absence de coupure. Toute conclusion « le yo-yo a disparu dans
l'ombre » serait un artefact.

L'ombre valide en revanche tout l'« open-loop » du nouveau code, et il
faut le faire AVANT le premier créneau réel :

| # | Métrique ombre | Cible GO |
|---|---|---|
| O1 | Hors épisode : `sh` ≡ v2 (traînée expirée) | identité stricte |
| O2 | Front de sortie de contrainte : `sh` part de `min(o_raw + R0, L)` puis pente vue = `Δo_raw − 0,15/s`, extinction ≤ R0/0,15 s | 100 % des sorties |
| O3 | Jamais `sh > L + 0,05` hors contrainte (cap) | 100 % |
| O4 | Purge contacteur-ouvert : aucune traînée active pendant une fenêtre contacteur ouvert | 100 % |
| O5 | number à 0 → `sh` ≡ v2 dès le cycle suivant | vérifié 1× |
| O6 | Aucun NaN, traînée jamais > 17 s (montre un état coincé) | zéro occurrence |

Les épisodes de contrainte se provoquent comme le 17/08 (clims +
piscine, voiture en charge sous v2). Une soirée suffit pour O1-O6.

## 6. Protocole du test réel minimal (boucle fermée)

Pré-requis : confiance saine (aucune entrée de défiance sur les 12 h
précédentes, détecteur muet), `contactor_cycles` relevé, trace 3 s
active, STOP à portée, kill-switch = number `twc_law_tail`.

**Reproduire les conditions du yo-yo de ce soir - c'est le seul test
qui prouve** : soirée, toutes clims (maison ~10 A pire phase), voiture
branchée consigne 16 A, équilibre attendu ~9-9,5 A, ACTIF-MAX,
créneau 30 min surveillé. La trace du 20:20-20:25 sert de témoin
direct (mêmes conditions, loi v2 pure).

| # | Métrique boucle fermée | Cible GO (témoin v2 entre parenthèses) |
|---|---|---|
| Y1 | Excursions publié > 21 par 5 min | ≤ 2 (témoin : 7) |
| Y2 | `contactor_cycles` sur le créneau | constant - zéro coupure, zéro morsure (témoin : 1 coupure) |
| Y3 | Amplitude / période du cycle voiture résiduel | ≤ ±1,5 A / ≥ 60 s (témoin : ±2,5 A / ~20 s) |
| Y4 | Défiance : tout ordre ≥ 21,45 soutenu est suivi d'effet ≤ 30 s | 100 % - la traînée n'a pas coûté la confiance |
| Y5 | Post-créneau : arrêt (biais pause) puis reprise autonome de session | reprise à la relâche, comme BEHAVIOR §8 |

Critères d'ABORT immédiat : première morsure OU deuxième excursion
> 21,9 sans descente voiture consécutive OU toute entrée de défiance →
`twc_law_tail` = 0 (retour v2 à chaud), STOP si l'épisode l'exige,
analyse de trace avant nouvel essai. GO 24 h ensuite (patron A11 du
TESTPLAN), puis report des constantes dans `40_LOI_DE_COMMANDE.md` §5
(nouvelle ligne « seuil d'action réel ~21,9 » et « tolérance intégrale
à +0,5 ») et leçon dédiée dans `contrat_electrique_LOGIQUE.md`.

## 7. Trade-offs assumés (à dire à voix haute)

1. **On accepte ~13 s de publié « optimiste » après chaque épisode**
   (la borne voit moins de marge qu'il n'y en a) : coût = un peu de
   charge perdue sur les transitoires, gain = plus de coupure. Le
   dimensionnement borne cette optimisme à R0 = 2 A max, décroissant.
2. **Un état ajouté** là où la doctrine (leçon 28) en vise zéro : il
   suit le SEUL patron d'état déjà validé (`capped_since_ms` :
   timestamp armé/purgé, jamais accumulé), avec purge sur les trois
   chemins (expiration, contacteur ouvert, fail-safe) et kill-switch.
3. **Le cap `min(·, L)` crée ≤ ~2 s de plat à L par sortie** : bien en
   deçà des 110 s de plat toléré mesurés ce soir dans la bande, et en
   zone « tient » où le plat est précisément le message voulu.
4. **La première excursion d'un échelon reste entière** : la traînée ne
   prétend pas empêcher la borne de voir un vrai dépassement - elle
   empêche seulement la sur-réaction de relâche qui entretenait le
   cycle. Les vrais excès prolongés continuent de remonter à la couche
   HA (pause/délestage) comme aujourd'hui.
