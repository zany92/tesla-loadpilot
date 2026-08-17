# Étude de conception — SYNTHÉTISEUR DE SIGNAL pour le DPM du TWC Gen 3

> **Document d'étude, 14/08/2026 — AUCUNE mise en œuvre.** Idée de Vincent :
> faire évoluer le firmware du KC868-A6 de « compteur fidèle » (sémantique
> RAW) vers un **synthétiseur de signal** — lire la téléinfo, PUBLIER un
> signal FAÇONNÉ, réaliste et crédible, conçu pour que le DPM natif de la
> borne module en douceur sans jamais couper. Évaluation rigoureuse,
> architecture recommandée, invariants de sécurité, plan de test
> incrémental réversible, estimation d'effort.
>
> Sources croisées : `40_LOI_DE_COMMANDE.md` (comportement mesuré),
> `contrat_electrique_LOGIQUE.md` (couche HA, leçons 1-27),
> `/config/esphome/kc868-a6-1.yaml` (vivant), dépôt amont
> `PVi1/esphome-twc-control` (clone du 14/08, HEAD `b445bcb`), notre
> adaptation `/config/esphome/twc-control.yaml`, fil HA community post #87
> (plausibilité 26.18), doc publique Enedis/Linky (dépassements).

> **ÉTAT (16/08/2026) — le document ci-dessous décrit l'étude ; la mise en
> œuvre a commencé.** E2 (estimateur + shadow) flashé le 15/08, tourne en
> mode **OMBRE** (sélecteur `twc_mode_signal`, boot = RAW, la borne voit le
> RAW). Buffer de sécurité **E5-lite** ajouté le 16/08 : number
> `twc_synth_buffer_pct` (0-30 %, défaut 10), coussin par phase
> `+(b/100)·max(0, 21 − (pub − Î))` inséré avant le clamp I1 — **formule
> « variante B » retenue** (coussin sur la marge MAISON : la réserve
> persiste à l'équilibre, pente de boucle = α conservée ; la variante sur la
> marge instantanée a été écartée, réserve qui s'évapore). Section vivante :
> `contrat_electrique_LOGIQUE.md` §6bis. **T2 prêt** — protocole complet
> (préconditions, déroulé, critères chiffrés, états de sortie) dans
> `61_SPEC_BUFFER_T2.md` (spec de l'agent architecte, 16/08).

---

## 0. Résumé exécutif

**Verdict : GO pour un POC par étapes — l'idée est théoriquement fondée et
dispose d'une preuve de terrain indirecte (PVi1).**

Le verdict « plafond du firmware » de `40_LOI_DE_COMMANDE.md` §5 a été
établi avec un signal à **gain de boucle 1** (RAW auto-référent : chaque
ampère pris par la voiture remonte intégralement dans la mesure publiée).
Un système discret bouclé à multiplicateur −1 est **marginalement stable** :
la quantification ~1 s du Linky, la latence et la cadence de décision du
firmware suffisent à entretenir l'oscillation jusqu'au trip. Ce n'est pas
(seulement) un plafond du firmware : c'est la signature d'un gain de boucle
trop élevé.

La preuve d'existence : **PVi1 a mesuré en réel** que le même firmware
borne, nourri d'un signal synthétique dont la composante « voiture » est
atténuée d'un gain k = 0,75 (< 1), **module durablement sous la consigne du
véhicule** — oscillation résiduelle bornée (~8-12 A), **zéro coupure** sur
des sessions de plusieurs minutes avec transitoires réels. Et il a mesuré
que le lissage temporel (EMA) du signal publié est **rejeté** par le
contrôle de plausibilité, alors qu'un gain multiplicatif sans retard est
accepté. Ces deux faits calibrent exactement ce qu'un synthétiseur a le
droit de faire.

L'architecture recommandée (§5) est un pipeline à 6 étages :
**mesure → découplage AC de la voiture (gain α < 1 sur les transitoires,
0 sur le continu) → feed-forward événementiel HA → extrapolation de
tendance → gouverneur de marge (coussin + plancher élastique) →
slew-limiter**, le tout DERRIÈRE le fail-safe et le biais existants,
inchangés, avec un kill-switch qui restitue la sémantique RAW actuelle à
l'identique.

Incertitude principale (à lever en premier, test T2 §10) : le contrôle de
plausibilité 26.18 accepte-t-il, en contexte import pur, un signal dont la
composante voiture est à gain 0,7-0,8 ET débarrassée de sa composante
continue ? PVi1 prouve le gain < 1 en contexte FVE ; le couplage AC est
notre extension. Si T2 échoue, la variante de repli V1 (PVi1 littéral,
gain constant, marge résiduelle sacrifiée) reste disponible.

---

## 1. Le problème, reformulé en termes de boucle

### 1.1 Modèle de la borne (tout mesuré, `40_LOI_DE_COMMANDE.md`)

- La borne polle nos registres toutes les **~190-200 ms** (mesuré en direct
  ce jour : 191 ms) et calcule `marge ≈ L − mesure_publiée` avec
  L = Max Conductor Limit (21 A). Elle **sait que la mesure l'inclut**.
- Servir : raisonnement sur la **moyenne** des 3 phases. Protéger :
  déclenchement sur la **pire phase** (`max(CT) > L`), réaction ≤ 5 s,
  coupure franche (contacteur ouvert 15-20 s), période de bang-bang ~55 s.
- Le véhicule répond au pilote en ~5 s (J1772) et rampe à ~0,65-1 A/s ;
  au redémarrage de session il ré-applique ses ampères mémorisés par lieu.
- Cadence de décision interne du firmware + réponse véhicule ⇒ au-delà de
  ~1 Hz de mesure, la latence n'est plus le facteur limitant (verdict
  14/08, 0,46 s).

### 1.2 Pourquoi le RAW bang-bang : gain de boucle

Signal RAW : `S = maison + I` (I = courant voiture). La borne asservit
`I → clamp(L − S)`. En discret :

```
I(n+1) = L − maison − I(n)        →  multiplicateur −1
```

Multiplicateur −1 = système **marginalement stable** : toute perturbation
(quantification 1 s du Linky, moyennage interne borne, latence, marche du
véhicule) entretient une oscillation qui ne s'amortit jamais — et dès que
`max(S) > L` un instant de trop : trip. C'est exactement les 4 campagnes de
latence du §5 de la loi de commande : améliorer la fraîcheur réduit
l'amplitude d'excitation mais ne change pas le multiplicateur. **Le
firmware n'est pas “incapable de tenir un palier” : il est incapable de
tenir un palier avec un signal à gain 1.**

Avec un gain α < 1 sur la composante voiture (`S = maison + α·I`) :

```
I(n+1) = L − maison − α·I(n)      →  multiplicateur −α, converge (|α|<1)
```

C'est la théorie. La section 2 montre que PVi1 l'a **vérifiée sur le
matériel réel**.

---

## 2. Analyse du code de PVi1 (la source d'inspiration demandée)

Clone du 14/08/2026, HEAD `b445bcb` (« docs: update README gain value and
trade-off notes to 0.75 »). Fichier unique `twc-control.yaml` (~43 Ko) +
README très documenté (historique de conception + confirmations live).

### 2.1 Ce qu'il publie, exactement

```
avail_main = main_breaker − real                (par phase, real = Shelly, borne INCLUSE)
avail_mode = GRID  : twc_breaker
             FVE   : k · (export : ⌊real⌋ ; import : −real)     k = self_balance_gain = 0,75
             FVE agrégé : max(strict_x, pool/3)  (crédit additif plafonné pool/3)
avail      = clamp( min(avail_mode, twc_breaker, avail_main), 0 … )
reported   = twc_breaker − avail                (clampé [0, twc_breaker])
puissance  = 230 × reported
```

- **Cadence** : recalcul à chaque push HA des 6 entités Shelly (Pro 3EM,
  push sur changement, sub-seconde) + tick filet 1 s ; publication en
  zero-order-hold entre deux recalculs ; la borne lit à ~200 ms/100 ms
  (post #78 : cadence resserrée à ~100 ms depuis 26.18).
- **La mesure inclut la borne** (pinces sur l'arrivée principale, exigé par
  sa formule `main_breaker − real`), comme chez nous.
- `reported` n'est **pas** du RAW : c'est une transformation affine de la
  réalité, à **pente 1** quand la contrainte main_breaker est active
  (`d reported/d real = 1` — corrélation parfaite), **plate à 0** quand la
  marge est ample (GRID non contraint), et à **pente k = 0,75** en FVE.

### 2.2 Comment il évite le rebond — les 4 leçons mesurées

1. **Jamais de moyenne inter-phases** (tentative 1) : la borne engage
   L1→L2→L3 séquentiellement ; diluer la pente d'une phase à ⅓ casse la
   corrélation → arrêt en quelques secondes. *Leçon : la corrélation est
   vérifiée PAR PHASE.*
2. **Jamais de lissage temporel** (tentative documentée puis annulée,
   commit `7b1c3f7` « Fix self-balancing oscillation with a lag-free gain,
   not smoothing ») : tout filtre EMA/passe-bas met le signal publié EN
   RETARD sur le courant réel de la borne pendant ses rampes → le contrôle
   de plausibilité se méfie et coupe (confirmé live : arrêts exactement
   quand la valeur lissée « rattrapait » un courant déjà changé). *Leçon
   capitale pour nous : le façonnage temporel est INTERDIT sur la
   composante voiture, autorisé partout ailleurs.*
3. **Le gain multiplicatif sans retard est ACCEPTÉ** : k recalculé à chaque
   cycle sur la lecture courante (aucun historique, aucun lag) → bouge en
   synchronisme avec la borne, pente réduite. `I(n+1) = k·E − k·I(n)`,
   multiplicateur −k, converge pour k < 1. Confirmé stable en live à 0,65
   et 0,75 (« no stopping », multi-minutes, transitoires réels) ; à k = 1 :
   bang-bang entretenu (« reported cycling ~13-16 A while TWC3 hunted
   between ~8-12 A, indefinitely » — SANS coupure franche, notez-le : le
   hunting à gain 1 chez lui restait sous le seuil de violation parce que
   reported est clampé ≤ twc_breaker).
4. **Escalade** : la borne descend très lentement vers « 0 A dispo » et
   peut tirer un résiduel indéfiniment → si les 3 phases restent épinglées
   à la limite 120 s d'affilée, il publie `twc_breaker + 0,1` pour forcer
   l'arrêt franc (30 s déclenchait à tort sur le transitoire de démarrage).

Le prix du gain k : à l'équilibre, la fraction `E/(1+k)` du surplus reste
inutilisée (~1,5 kW mesuré à 0,75) — le gain s'applique aussi au continu.
**C'est le défaut que notre couplage AC (§5.2) corrige.**

Et son plancher : k trop bas rétrécit la cible sous le minimum borne
(mesuré : k = 0,5 → cible 3,5 A → la charge ne démarre jamais ; minimum
TWC ~5 A selon lui, ~6 A mesuré chez nous côté véhicule).

### 2.3 « Régulation dynamique en mode GRID » — ce qui est réellement démontré

En GRID, `reported = max(0, twc_breaker − (main_breaker − real))` : pente 1
quand la contrainte est active — donc **même gain de boucle 1 que notre
RAW**. Sa confirmation GRID (« charging current visibly drops when
household load increases », « keeps responding continuously ») démontre que
la borne suit le signal en continu pendant toute la session, pas qu'elle
tient un palier sous la consigne en régime contraint permanent. La
modulation sous-consigne durable, stable et sans coupure n'est démontrée
que par sa boucle FVE **à gain 0,75**. C'est cohérent avec notre loi de
commande, et c'est précisément le levier à transposer.

### 2.4 Notre trajectoire vs l'amont

- Notre adaptation `/config/esphome/twc-control.yaml` (12/08) est
  **fidèle** : transformation `reported = breaker − avail`, gain 0,75,
  escalade, modes GRID/FVE/agrégé conservés (matériel seul adapté).
- Le vivant `kc868-a6-1.yaml` (13-14/08) a **abandonné la transformation**
  au profit du RAW + biais, par crainte du contrôle de plausibilité
  (« plateau figé peu plausible », en-tête §2.4 de `20_FIRMWARE.md`). Avec
  le recul des mesures PVi1 : ce qui est rejeté, c'est le **statique** et
  le **retardé** — pas le synthétique à pente correcte. Le balancier peut
  revenir, mieux armé.

---

## 3. Le contrôle de plausibilité 26.18 : ce qu'on sait, ce qu'on ignore

**Établi (mesures PVi1 + fil HA #78/#87 + nos essais)** :

| Signal publié | Verdict borne |
|---|---|
| RAW quantifié ~1 s, latence 0,3-1,1 s (nous) | ACCEPTÉ (la charge tourne ; le problème est l'oscillation, pas le rejet) |
| Pente 1 par phase (PVi1 GRID contraint) | ACCEPTÉ |
| Pente 0,75 par phase, sans retard (PVi1 FVE) | ACCEPTÉ |
| Constante (maître OFF, 0 A figé) | REJETÉ en quelques secondes de session → repli plafond interne |
| Moyenne inter-phases (dilution pente ⅓) | REJETÉ (arrêt quelques secondes après démarrage) |
| Lissé EMA (retard sur les rampes borne) | REJETÉ (arrêts corrélés au rattrapage du filtre) |
| Cadence de lecture | ~100 ms depuis 26.18 (post #78) ; nos polls : 191 ms mesurés |

**Inconnu (à lever expérimentalement, T2)** : la fenêtre exacte de
corrélation (durée, seuil de pente minimale, tolérance au bruit maison),
et le verdict sur : pente α pendant les rampes + suppression LENTE de la
composante continue voiture (τ ≈ 60 s). Argument pour l'acceptation : vu
de la borne, une dérive lente de la « maison » est indiscernable d'un
équipement réel qui s'allume/s'éteint — le bruit maison décorrélé est
présent sur tout vrai compteur ; ce que la borne vérifie, c'est que SA
rampe se reflète, pas que rien d'autre ne bouge. Argument pour la
prudence : personne ne l'a testé. D'où la place de T2 en tête du plan.

---

## 4. Évaluation des pistes demandées

### 4.1 Découplage total « maison seule » (α = 0) — DÉCONSEILLÉ tel quel

Publier `maison = Linky − I_voiture` supprime la boucle (gain 0), mais :

- **Plausibilité** : le signal ne reflète plus DU TOUT les rampes de la
  borne — c'est le cas le plus proche du « statique » rejeté. Risque
  maximal de repli au plafond interne (= plus aucun contrôle).
- **Résidu d'erreur** : l'estimation `Î` du courant voiture (vitals HA
  2 s, ou modèle interne) est en retard pendant les rampes ; l'erreur
  `e = I − Î` passe à 100 % dans le signal publié (fuite de la voiture
  dans « maison » : ~2 A à 2 s de retard × 1 A/s). La borne verrait la
  maison « monter » à chacune de ses propres rampes — corrélation
  inversée, précisément le motif suspect.
- Aucun bénéfice de stabilité au-delà de α petit.

**Conservé comme brique** : le découplage PARTIEL (α ∈ [0,6 ; 0,85]),
où l'erreur d'estimation ne pèse plus que (1−α)·e ≈ 0,5 A (§5.2).

### 4.2 Façonnage temporel — OUI, mais jamais sur la composante voiture

La leçon PVi1 n°2 est une contrainte dure : slew-limiter, interpolation,
prédiction s'appliquent à la composante **maison + coussin** uniquement.
La composante α·I traverse sans retard (elle est déjà à jour à ±1 s via le
Linky, ±2 s via vitals — c'est le niveau de retard que la borne tolère
aujourd'hui en RAW). Détail §5.4-5.6.

### 4.3 Coussin piloté + élasticité Enedis — OUI (gouverneur de marge)

Le biais actuel EST un coussin : le généraliser en gouverneur continu est
naturel (§5.5). Élasticité documentée :

- **Officiel** (Enedis, FAQ + spécifications de comptage) : surveillance
  **par phase** en triphasé ; l'organe de coupure est calibré « en
  cohérence avec les courbes de protection thermique des disjoncteurs »
  — tolérance d'environ 10 % + **délai inversement proportionnel à
  l'amplitude** du dépassement (un pic de démarrage de quelques secondes
  ne coupe pas). Champ TIC standard `PCOUP` (puissance de coupure) et
  registre STGE bit 7 (« dépassement EN COURS ») = la vérité du compteur
  en temps réel. Référence à sourcer proprement pour publication :
  Enedis-NOI-CPT_54E (déjà notée au sommaire).
- **Mesuré chez nous** (`contrat_electrique_LOGIQUE.md` §1) : coupure à
  partir de ~1,3× la limite d'une phase, ~200 s à 1,4×, quelques secondes
  sur dépassement massif. **Ce sont les valeurs de dimensionnement** (le
  mesuré prime sur le documenté).

Budget d'élasticité proposé : intégrateur par phase
`J = ∫ max(0, VA_phase − 5000) dt`. Point de calibration mesuré :
2000 VA d'excès × 200 s ≈ 400 kVA·s au trip → **budget de conception
J_max = 60 kVA·s par phase (15 % du trip)**, réservé aux excursions
transitoires pendant les descentes de modulation (ex. 600 VA d'excès
pendant 100 s). Au-delà, ou dès que STGE bit 7 s'allume : plancher et
coussin relâchés, retour au comportement conservateur (§6, I4).

### 4.4 Anti-décrochage (plancher de marge ~6 A) — OUI, borné et budgété

Publier au plus `L − 6,5 A` par phase (marge présentée ≥ 6,5 A) tant que
les invariants le permettent : la borne ne voit JAMAIS la marge passer
sous le minimum véhicule → **le DPM n'a plus jamais de raison de couper**.
La sous-déclaration que cela implique quand la réalité est tendue est
bornée par le budget J et par le coussin_max (§6, I1) ; les vraies
urgences restent gérées au-dessus (pause = biais plein, qui PRIME sur le
plancher — §6, I6) et par le fail-safe (inchangé).

### 4.5 Feed-forward événementiel + extrapolation (addendum Vincent) — OUI, cœur de l'architecture

Développés en §5.3-5.4. Point de théorie demandé — **pourquoi le
feed-forward ne peut pas osciller** : une boucle oscille quand la sortie
du système revient à son entrée avec un gain et un retard (ici : signal
publié → pilote borne → courant voiture → Linky → signal publié). Le terme
de feed-forward `FF(t)` est fonction d'**événements d'état HA**
(allumage/extinction d'équipements) qui ne dépendent ni du courant
voiture, ni du signal publié : il n'existe AUCUN chemin de retour de la
sortie vers ce terme. Formellement, `S = maison + FF + α·I` ne change pas
le multiplicateur de boucle (−α, inchangé par FF) : le feed-forward
translate le point d'équilibre sans toucher à la dynamique. Son seul mode
d'échec est une erreur d'AMPLITUDE ou de CHRONOLOGIE (double comptage
pendant le crossfade, injection fantôme si l'appel de courant ne se
matérialise pas) — et ces erreurs sont dans le **sens sûr** (sur-déclarer
→ la borne réduit trop → confort dégradé, jamais un danger), bornées par
un TTL et un plafond d'injection (§5.3).

---

## 5. Architecture recommandée : le synthétiseur à 6 étages

```
                         ┌────────────────────────────────────────────────┐
  UDP olimex ~1 Hz ──►   │ E1 FUSION DES SOURCES (inchangé)               │
  miroir HA (secours) ─► │ UDP frais > miroir HA > FAIL-SAFE main_breaker │
                         └──────────────┬─────────────────────────────────┘
                                        │ maison+voiture par phase (RAW)
  vitals borne (HA, 2 s) ─┐             ▼
  contacteur (miroir) ────┤  ┌────────────────────────────────────────────┐
                          └► │ E2 DÉCOUPLAGE AC : Î voiture (estimateur)  │
                             │ base = RAW − (1−α)·(Î − Î_lente)           │
                             │ → pente α sur les rampes, 1:1 sur le DC    │
                             └──────────────┬─────────────────────────────┘
  événements HA (gains ──────►┌─────────────▼─────────────────────────────┐
  calibrés par équipement)    │ E3 FEED-FORWARD ÉVÉNEMENTIEL              │
                              │ injection immédiate ± crossfade vers la   │
                              │ mesure, TTL, plafond, par phase           │
                              └─────────────┬─────────────────────────────┘
                              ┌─────────────▼─────────────────────────────┐
                              │ E4 EXTRAPOLATION DE TENDANCE (maison)     │
                              │ pente Linky ×β, horizon ≤1 s, MONTÉE seule│
                              └─────────────┬─────────────────────────────┘
                              ┌─────────────▼─────────────────────────────┐
  réglages HA (numbers) ────► │ E5 GOUVERNEUR DE MARGE                    │
  STGE bit 7, budget J ─────► │ + coussin (marge de sécurité pilotée)     │
                              │ − plancher (marge présentée ≥ 6,5 A)      │
                              └─────────────┬─────────────────────────────┘
                              ┌─────────────▼─────────────────────────────┐
                              │ E6 SLEW-LIMITER (maison+coussin seuls)    │
                              │ ouverture de marge lente, fermeture libre │
                              └─────────────┬─────────────────────────────┘
                                            ▼
                                 + biais (rampe lot 13, INCHANGÉ, prime)
                                            ▼
                                registres Modbus (ZOH, poll ~191 ms)
```

Kill-switch global `twc_synth_enabled` (défaut OFF au déploiement) : OFF =
tous les étages E2-E6 court-circuités = **sémantique RAW actuelle à
l'identique**, biais et fail-safe inclus.

### 5.1 E1 — Fusion des sources : inchangée

La priorité UDP frais > miroir HA > fail-safe, les drapeaux `*_seen`, le
debounce 10 s, l'init à `main_breaker` : rien ne bouge. Le synthétiseur
consomme la sortie de cette fusion. En source FAILSAFE ou maître OFF, les
étages E2-E6 sont ignorés (I2).

### 5.2 E2 — Découplage AC de la voiture (le cœur)

**Estimateur Î du courant voiture** (par ordre de priorité) :

1. `sensor.tesla_wall_connector_phase_a/b/c_current` mirrorés (package
   REST vitals, 2 s — vérifiés vivants ce jour : 12,1/12,1/12,2 A pendant
   la charge en cours) ;
2. entre deux pushes : **modèle interne** — Î suit la dernière valeur
   vitals, bornée par les slews mesurés du couple borne+véhicule (montée
   ≤ 1 A/s, descente ≤ 1 A/s hors coupure ; contacteur ouvert (miroir
   lot 13) → Î := 0 immédiatement) ;
3. vitals indisponibles > 10 s → **repli α := 1** (le découplage se
   neutralise, on retombe sur du RAW façonné — dégradation douce, I7).

**Transformation** (par phase p) :

```
Î_lente = EMA(Î, τ_dc = 60 s)              # composante continue voiture
base_p  = RAW_p − (1−α)·(Î_p − Î_lente_p)  # α ≈ 0,75 (number HA, 0..1)
```

Propriétés :

- **Pendant une rampe borne** (Î bouge, Î_lente ~immobile) :
  `d base/d I = 1 − (1−α)·(dÎ/dI) ≈ α` → multiplicateur de boucle −α,
  **convergence** ; corrélation par phase préservée à pente α (précédent
  PVi1 : 0,75 accepté).
- **En régime établi** (Î → Î_lente) : `base = RAW` → la composante
  continue de la voiture est publiée 1:1 → **aucune marge gaspillée**
  (correction du défaut `E/(1+k)` de PVi1 : son gain s'applique au
  continu, le nôtre seulement aux transitoires).
- **Résidu d'erreur d'estimation** : `e = I − Î` (borné par
  retard_vitals × rampe ≈ 2 s × 1 A/s = 2 A) n'entre dans `base` qu'avec
  le poids (1−α) ≈ 0,5 A. Pendant les rampes, ce résidu s'ajoute à la
  composante « maison » perçue — amplitude négligeable devant le bruit
  maison réel, et toujours dans le sens transitoire (il se résorbe quand
  vitals rattrape).
- La suppression DC est LENTE (τ 60 s) : ce n'est pas un retard sur les
  rampes (leçon PVi1 n°2 respectée), c'est une dérive du fond — vue borne,
  indiscernable d'un équipement maison qui évolue.

**Analyse de stabilité complète** (régime contraint, borne asservit
`I → L − S`) : en posant `δ = I − Î_lente`,
`δ(n+1) = −α·δ(n) + perturbations` → réponse apériodique amortie pour
α < 1 ; la voie lente (τ_dc) déplace l'équilibre vers
`I* = L − maison − coussin` (utilisation complète de la marge) avec une
constante de temps ~τ_dc, sans terme intégral instable (l'EMA est
strictement passive). Deux échelles de temps découplées : rapide (−α,
sub-10 s), lente (τ_dc, ~1 min) — séparation > 6× ⇒ pas d'interaction.

### 5.3 E3 — Feed-forward événementiel (addendum, dimension centrale)

**Canal HA → ESP.** Trois capteurs `platform: homeassistant` sur le kc868
(`sensor.contrat_elec_ff_phase_1/2/3_va`), alimentés côté HA par un
template à déclencheur qui somme les injections actives. Latence du canal :
push API natif ESPHome, événementiel, **~50-300 ms** en LAN (même
mécanisme que le miroir Linky actuel, médiane mesurée bien < 1 s) — à
comparer aux **2-10 s** que met l'appel de courant réel à se matérialiser
dans le Linky (montée physique du compresseur + refresh interne 1 s +
transport 0,3 s). Gain net d'anticipation : **2 à 8 s**. Fiabilité : perte
API → capteur en NAN → injection ignorée (repli = comportement actuel) ;
la fraîcheur est jugée comme pour le miroir Linky (staleness 10 s → FF
neutralisé). Pas besoin d'un second canal UDP : le FF n'exige pas la
latence de la mesure (l'événement précède la physique de plusieurs
secondes) — et l'API est déjà là. Option future si besoin : ajouter les 3
grandeurs FF au flux `packet_transport` d'un nœud ESPHome, mais HA ne
parle pas packet_transport nativement — l'API reste le bon canal.

**Côté HA (nouveau, ~150 lignes de package)** : une automatisation par
famille d'équipements observables — clims Faikin (4 unités, gains
calibrés `contrat_elec_gain_clim_*_va` ≈ 700 VA, phase 3 + pigeonnier),
pompe piscine (420 VA, phase 2), électrolyseur (50 VA, phase 2),
surpresseur (1330 VA, phase 1), chauffe-eau (par plage horaire/pattern,
phase 1), pompe de forage (1000 VA, phase 1 — l'ESP la connaît même en
direct : c'est LUI qui la pilote). À l'ALLUMAGE : injection
`+gain_va` sur la phase mappée (`input_select.contrat_elec_phase_*`),
horodatée. À l'EXTINCTION : injection négative symétrique ? NON —
l'extinction se voit dans le Linky en ~1-2 s et une marge qui S'OUVRE
n'a jamais fait tripper personne : **aucune injection à l'extinction**
(la remontée douce est déjà garantie par le slew-limiter E6 qui ralentit
l'ouverture de marge). Simplicité et sûreté.

**Décroissance / crossfade anti-double-comptage.** L'injection ne doit pas
compter double quand la mesure réelle monte. Deux mécanismes combinés,
côté ESP :

```
w(t) = clamp( (RAW_p(t) − RAW_p(t_event)) / gain_va , 0, 1 )   # part déjà matérialisée
FF_p(t) = gain_va × (1 − w(t))                                  # le complément seulement
FF_p := 0 après TTL (45 s) ou si w a atteint 1                  # injection fantôme purgée
```

`w` est calculé sur la mesure de la phase concernée depuis l'événement :
au fur et à mesure que le compresseur monte, l'injection s'éteint
exactement d'autant — la somme `RAW + FF` transite continûment de
« prédiction » à « mesure » sans marche. Cas dégénérés : deux événements
rapprochés sur la même phase → les injections s'additionnent, chaque `w`
référencé à son propre `t_event` (2 slots par phase suffisent, au-delà on
fusionne) ; baisse de la maison pendant la fenêtre (autre équipement
s'éteint) → w sous-estime la matérialisation → sur-déclaration temporaire
≤ gain_va ≤ TTL : sens sûr. Plafond global d'injection :
`FF_p ≤ 2000 VA` (I5).

**Charges NON observables** (AGA ~1,7 kVA cyclique, four, bouilloire —
toutes phase 1, aucun capteur) : deux parades cumulables :
1. **prédiction par pente** = E4 (ci-dessous) — la rafale AGA monte en
   1-2 s, l'extrapolation en gagne ~1 ;
2. **coussin dynamique par phase** (E5) : `coussin_p1 > coussin_p2/p3`
   (ex. 2 A vs 1 A), réglable — la phase 1 vit structurellement plus loin
   du précipice. À terme, un pattern horaire (heures de cuisine) peut
   moduler ce coussin depuis HA sans toucher au firmware (c'est un
   number).

**Stabilité** : démontrée §4.5 — FF est hors boucle (aucun chemin
sortie→FF), il translate l'équilibre sans changer le multiplicateur −α.
Ses erreurs sont bornées (plafond, TTL) et de sens sûr (sur-déclaration).

### 5.4 E4 — Extrapolation de tendance (entre les ticks Linky)

La borne lit à ~191 ms un signal qui ne change que toutes les ~1 s
(quantification Linky) : elle voit des marches. Un vrai Neurio bouge à
chaque poll. Synthèse d'un signal continu :

```
pente_p = (maison_p(t_n) − maison_p(t_n−1)) / Δt          # sur la COMPOSANTE MAISON (base+FF)
maison_synth_p(t) = maison_p(t_n) + β × max(0, pente_p) × min(t − t_n, 1 s)
```

- **β ≈ 0,5** (number HA), horizon ≤ 1 s (au tick suivant la vraie valeur
  reprend la main — l'erreur d'extrapolation ne s'accumule jamais) ;
- **montée seulement** (`max(0, pente)`) : extrapoler une DESCENTE
  publierait sous la réalité (sous-déclaration non nécessaire) et ouvrirait
  la marge en avance (invitation à ramper) — asymétrie de sécurité ;
  en descente : zero-order-hold, le slew E6 gère la douceur ;
- recalculée au tick synthétiseur (200-250 ms), servie par les
  read_lambdas via les globals habituels (aucun calcul dans la lambda,
  deadline 66 ms intouchée) ;
- appliquée à la composante maison APRÈS découplage : les marches de la
  voiture, elles, sont déjà à pente α sans retard (E2) — on n'extrapole
  jamais la voiture (leçon PVi1 n°2).

Effet : la borne voit un signal fluide qui **devance légèrement la réalité
en montée** — exactement le comportement d'un compteur rapide, synthétisé,
et ~0,5-1 s d'anticipation gratuite sur les charges non observables.

### 5.5 E5 — Gouverneur de marge : coussin + plancher élastique

```
S_p = maison_synth_p + α·(Î_p − Î_lente_p) + Î_lente_p + coussin_p     # coussin_p ≥ 0
S_p = min(S_p, L − marge_plancher)   si  plancher_autorisé              # marge présentée ≥ 6,5 A
```

(équivalent : `S = base_synthétisée + coussin`, plafonnée à `L − 6,5`.)

- **Coussin** (`coussin_p` : numbers HA par phase, défauts 1/1/2 A —
  phase 1 plus grand, §5.3) : la borne croit la maison plus chargée
  qu'elle n'est → elle sert le véhicule à distance du précipice. C'est le
  biais actuel, généralisé en continu et par phase. Pendant une montée
  maison réelle, la vraie pointe peut dépasser transitoirement 100 % du
  contrat PENDANT que la modulation descend — c'est le rôle assumé de
  l'élasticité Enedis (budget J, §4.3) : on échange « coupure DPM
  brutale » contre « excursion courte tolérée par le Linky ».
- **Plancher** (`marge_plancher = 6,5 A`, autorisé si : biais == 0 ET
  budget J_p < J_max ET STGE bit 7 éteint ET source ≠ FAILSAFE) : la marge
  présentée ne passe jamais sous le minimum véhicule → **zéro coupure
  DPM**. Quand le plancher écrête (réalité tendue), on sous-déclare : la
  différence `réalité − S` est le « prêt élastique », intégré dans J et
  remboursé dès que la couche HA (pause biais plein, délestage) ou la
  baisse naturelle ramène la réalité sous `L − 6,5 − coussin`. Le plancher
  n'est PAS un droit permanent : c'est un amortisseur temporel qui donne à
  la couche lente (HA, 30 s) le temps d'agir proprement au lieu de laisser
  le DPM trancher au contacteur.
- STGE bit 7 (déjà décodé côté HA, et le registre transite par l'UDP
  olimex à terme si besoin — aujourd'hui : miroir HA suffit, le bit est
  une urgence à l'échelle 10 s) → plancher ET coussin relâchés, S := RAW
  (pass-through), la machinerie HA existante (escalade STGE 3 crans)
  garde la main.

### 5.6 E6 — Slew-limiter de publication

Sur la composante `maison_synth + coussin` uniquement (jamais sur α·Î) :

```
fermeture de marge (S qui MONTE)  : libre jusqu'à 3 A/s   # réduire vite est sûr
ouverture de marge (S qui DESCEND): ≤ 0,5 A / 5 s          # même loi que la rampe de biais lot 13
```

- Une marge qui se rouvre lentement = le véhicule rampe par petites
  marches qu'il suit sans jamais les dépasser — généralisation directe de
  la rampe de biais (qui a éliminé les 58 alertes/jour) à TOUT le signal.
- Une marge qui se ferme sans limite dure = réponse immédiate aux montées
  maison (avec E3/E4 qui l'anticipent déjà).
- 3 A/s en fermeture = continuité vue borne (0,6 A par poll de 191 ms),
  jamais un échelon.
- Exception : biais plein (pause) et fail-safe COURT-CIRCUITENT le slew
  (un arrêt d'urgence ne se lisse pas) — comme aujourd'hui.

### 5.7 Tick, CPU, deadline 66 ms

- Nouveau tick `interval: 250ms` exécutant tout le pipeline (E2-E6 : une
  trentaine d'opérations flottantes et quelques branches — ordre de
  grandeur 10-50 µs sur ESP32 à 240 MHz) + les triggers événementiels
  existants (UDP on_value, pushes HA) inchangés.
- Les `read_lambda` Modbus restent des `return id(global);` stricts —
  AUCUN calcul ajouté sur le chemin de réponse. La deadline 66 ms n'est
  pas concernée par le synthétiseur (vérification tout de même par le
  capteur `TWC Poll Interval` en QA, comme au lot UDP).
- Interdits reconduits : pas de log par tick (piège VERBOSE du 13/08),
  pas d'allocation dynamique dans le pipeline, pas d'émission réseau
  depuis ce nœud.
- Capteur diagnostic nouveau : `TWC Synth Loop µs` (micros() autour du
  pipeline, filet update 5 s) — budget d'alerte : > 5 ms.

---

## 6. Invariants durs de sécurité (non négociables)

| # | Invariant | Mécanisme |
|---|---|---|
| **I1** | **Jamais publier sous `réalité − coussin_max`** : `S_p ≥ RAW_p − sous_decl_max_p` avec `sous_decl_max_p` = 4 A (~920 VA), très en deçà de l'excès de calibration du trip Linky (2000 VA → 200 s) | clamp final du pipeline, AVANT écriture des globals ; la seule source de sous-déclaration est le plancher E5, déjà budgété |
| **I2** | **Fail-safe intouché** : aucune source saine → `S = main_breaker`, marge 0. Le synthétiseur ne s'exécute qu'en branche normale | ordre des branches de `recompute_ct` conservé |
| **I3** | **Le biais prime sur tout** : biais plein (pause HA) ⇒ `S ≥ L` ⇒ arrêt franc, plancher désactivé, slew court-circuité | plancher conditionné à `biais == 0` ; biais ajouté APRÈS le plancher |
| **I4** | **Budget d'élasticité** : `J_p = ∫max(0, VA_réel_p − 5000)dt ≤ J_max` (60 kVA·s, number HA) sinon plancher relâché ; STGE bit 7 ⇒ pass-through RAW immédiat, quels que soient J et le reste | intégrateur par phase dans le pipeline, reset après 5 min sous la limite |
| **I5** | **Feed-forward borné** : `FF_p ≤ 2000 VA`, TTL 45 s, injection uniquement POSITIVE (jamais d'ouverture de marge par FF) | clamp + horodatage par slot |
| **I6** | **Plancher conditionnel** : actif seulement si biais == 0 ET J < J_max ET STGE éteint ET source ∈ {UDP, HA} | garde unique dans E5 |
| **I7** | **Dégradation en échelle** : vitals morts → α := 1 ; FF stale → FF := 0 ; synth OFF → RAW exact ; sources mortes → fail-safe. Chaque étage tombe sur l'étage du dessous, jamais sur un état nouveau | replis codés par étage |
| **I8** | **Boot sûr** : globals init à `main_breaker`, synthétiseur inerte tant que la première mesure ET (si α < 1) le premier vitals ne sont pas vus ; `twc_synth_enabled` avec `restore_mode: RESTORE_DEFAULT_OFF` pendant toute la phase d'essais | drapeaux `*_seen` étendus |
| **I9** | **Pas de NaN, pas de négatif** : chaque étage clamp sa sortie ; NaN en entrée = étage neutralisé | gardes `isnan` systématiques (piège auto-parse déjà connu) |
| **I10** | **Corrélation jamais retardée** : aucun filtre temporel (slew, EMA, extrapolation) sur le terme α·Î ; τ_dc ≥ 60 s figé en dur (pas un number, pour interdire un réglage dangereux) | structure du pipeline |

Le pire cas composite (FF fantôme au plafond + coussin max + extrapolation
max) est une SUR-déclaration ≈ 2000 VA + 2 A + 1 A pendant ≤ 45 s → la
borne réduit le véhicule trop fort → au pire une pause de confort — jamais
un risque contrat. Le pire cas de SOUS-déclaration est borné par I1/I4 et
couvert par l'élasticité mesurée avec un facteur ≥ 6 (60 vs 400 kVA·s), et
par l'étage HA au-dessus (alerte 90 %, pause 97 %, délestage) qui, lui,
raisonne toujours sur la MESURE VRAIE (le package lit l'olimex, pas notre
signal publié — séparation des vérités à préserver, à documenter dans le
package : **ne jamais brancher les automatisations HA sur les capteurs
`TWC Published *`**).

---

## 7. Pseudo-code du synthétiseur (tick 250 ms, par phase p ∈ {1,2,3})

```c
// ---------- E2 : découplage AC ----------
if (vitals_frais) {                      // push HA < 10 s
  I_hat[p] = vitals[p];
} else if (contacteur_ouvert)  I_hat[p] = 0;
else  I_hat[p] = clamp(I_hat[p], I_hat[p]-1.0f*dt, I_hat[p]+1.0f*dt);  // modèle borné
alpha_eff = vitals_ok ? alpha : 1.0f;                                  // I7
I_dc[p]  += (dt/60.0f) * (I_hat[p] - I_dc[p]);                         // EMA τ=60 s
base      = RAW[p] - (1.0f - alpha_eff) * (I_hat[p] - I_dc[p]);

// ---------- E3 : feed-forward ----------
ff = 0;
for (slot : ff_slots[p]) {
  if (now - slot.t0 > FF_TTL) { slot.actif = false; continue; }
  w = clamp((RAW[p] - slot.raw0) / slot.gain, 0.0f, 1.0f);
  ff += slot.gain * (1.0f - w);
}
ff = min(ff, FF_MAX);                                                  // I5
maison = base - alpha_eff*(I_hat[p]-I_dc[p])  /* part maison de base */ ;
// (en pratique on façonne base+ff d'un bloc, le terme voiture étant
//  ajouté en dernier — cf. E6)

// ---------- E4 : extrapolation (montée seule, composante maison) ----------
pente   = (maison_now - maison_prev) / dt_linky;         // par tick Linky
synth   = maison_now + BETA * max(0.0f, pente) * min(now - t_linky, 1.0f);

// ---------- E5 : gouverneur ----------
S = synth + ff + coussin[p];
plancher_ok = (biais_applique == 0) && (J[p] < J_MAX) && !stge_bit7
              && source_saine;                                         // I6
if (plancher_ok)  S = min(S, L - MARGE_PLANCHER);        // 21 - 6.5
J[p] += dt * max(0.0f, VA_reel[p] - 5000.0f);            // budget élasticité (I4)
if (calme_5min)   J[p] = 0;
if (stge_bit7)    S = maison_now;                        // pass-through (I4)

// ---------- E6 : slew (maison+coussin seuls) puis terme voiture ----------
S = slew(S, montee_max = 3.0f*dt, descente_max = 0.1f*dt);   // 0,5 A / 5 s
S = S + alpha_eff * (I_hat[p] - I_dc[p]) + I_dc[p];          // voiture : JAMAIS lissée (I10)

// ---------- garde finale ----------
S = max(S, RAW[p] - SOUS_DECL_MAX);                          // I1
S = max(S, 0.0f);  if (isnan(S)) S = RAW[p];                 // I9
S = S + biais_applique;                                      // I3 (rampe lot 13 inchangée)
ct_current[p] = S;  ct_power[p] = S * 230.0f;
```

(~120 lignes C réelles avec l'état des slots FF et l'observabilité ;
`recompute_ct` actuel conservé comme branche `synth OFF`.)

---

## 8. Cohabitation avec l'existant

| Existant | Devenir avec le synthétiseur |
|---|---|
| **Contrôleur Fleet (Whale)** | Rétrogradé de « régulateur » à **gestionnaire de session** si T2-T5 valident : démarrage/arrêt, relance post-« charging failed » (G.12 — reste indispensable : le synthétiseur supprime les coupures DPM mais pas les pauses volontaires), plafond utilisateur, départ/arrivée. La modulation fine deviendrait **100 % locale et universelle** — c'est l'enjeu : un seul chemin de modulation pour Whale ET invités, plus de budget 150 cmd/j consommé par la régulation, plus de dépendance au réveil cloud. Décision de rétrogradation SEULEMENT après T5 (soak 24 h) — d'ici là les deux coexistent, le synthétiseur rendant simplement le travail du contrôleur plus rare (il n'interviendra plus que quand la cible de confort 85 % exige moins que ce que la marge physique permet). |
| **Mode `borne_seul`** | Devient le **harnais de test naturel** du synthétiseur (Whale traitée en invité, zéro commande cloud) — c'est exactement la configuration des tests T2-T4. À terme : mode nominal possible. |
| **Pause binaire (biais plein)** | **Ultime filet, inchangé** (I3) : le synthétiseur en a BESOIN — quand la vraie marge est < 6 A durablement, le plancher s'épuise (budget J) et c'est la pause propre, avec mémo de demande et relâche projetée, qui prend le relais. La hiérarchie devient : synthétiseur (continu, 250 ms) → contrôleur/consignes (30 s) → pause binaire (dernier recours) → fail-safe. |
| **Rampe de biais lot 13** | Conservée telle quelle (le biais reste le canal de pause) ; le slew E6 en est la généralisation pour le reste du signal. À terme les deux pourraient fusionner — pas au POC. |
| **Plausibilité 26.18** | Le signal façonné RESTE corrélé à l'action de la borne : pente α par phase pendant ses rampes, sans retard (I10). Les composantes non corrélées (FF, extrapolation, coussin) sont indiscernables du bruit maison d'un vrai compteur. Zones d'ombre → T2 avec critères d'abandon nets. |
| **Package HA (seuils, alertes, délestage)** | Inchangé — il raisonne sur la mesure VRAIE (olimex), jamais sur le signal publié. Ajouts : capteurs FF, numbers de réglage synth, une automatisation FF (~150 lignes). |
| **Publication `tesla-loadpilot`** | Le synthétiseur serait le « module 3 » du dépôt — mais PAS avant validation complète ici. L'étude elle-même (boucle à gain α, couplage AC, FF hors boucle) est du contenu original fort pour `control-law.md`. |

---

## 9. Risques et parades

| Risque | Gravité | Parade |
|---|---|---|
| Plausibilité rejette α < 1 en import pur → borne au plafond interne (plus AUCUN contrôle DPM) | Haute (c'est LE risque) | T2 en premier, véhicule Whale, surveillance `TWC Polling Active` + courant borne vs marge attendue ; critère d'abandon : borne ignore le signal > 2 min → synth OFF (retour RAW immédiat) ; repli V1 = gain constant PVi1 (terrain-prouvé) en acceptant la marge résiduelle perdue |
| Sous-déclaration mal bornée → disjonction Enedis réelle | Critique mais bien bornée | I1 (4 A max), I4 (budget J 15 % du trip mesuré), STGE pass-through, couche HA sur mesure vraie ; le réarmement Linky est un appui long « + » (désagrément, pas un danger) |
| Double comptage FF pendant le crossfade | Faible | sens sûr (sur-déclaration), TTL 45 s, plafond 2 kVA |
| Estimateur Î faux (vitals figés, WiFi) | Moyenne | staleness 10 s → α := 1 (RAW façonné) ; contacteur ouvert → Î = 0 ; erreur résiduelle pondérée (1−α) |
| CPU/tick 250 ms perturbe le Modbus | Faible | pipeline ~µs, read_lambdas intouchées, capteur `Synth Loop µs`, QA poll ~191 ms stable |
| Reboot ESP pendant une charge | Faible | I8 : boot = main_breaker (existant), synth inerte avant première mesure+vitals ; règle « jamais flasher pendant une charge » reconduite |
| MAJ firmware TWC change le contrôle | Moyenne | constantes = propriétés mesurées (déjà documenté) ; après toute MAJ borne : repasser T1-T2 avant de réactiver ; kill-switch à portée de main |
| « Charging failed » après pauses répétées | Existant | inchangé — G.12 couvre ; le synthétiseur RÉDUIT le nombre de pauses donc le risque |
| Complexité (10 réglages de plus) | Moyenne | défauts figés + page réglages dédiée ; α, β, coussin, J_max en numbers ; TOUT le reste en dur |

---

## 10. Plan de test incrémental — chaque étape réversible

Principe : un switch par étage, `twc_synth_enabled` global défaut OFF,
retour au RAW = 1 clic à tout instant. Mode manuel biais (lot 13 B3) ON
pendant les tests actifs pour geler les écritures HA. Véhicule d'essai =
Whale, `borne_seul` ON, plafond 16 A. Instrumentation existante : compteur
de cycles contacteur (lifetime borne), `TWC Poll Interval`, vitals 2 s,
traces WS.

| T | Contenu | Ce qu'on branche | Critère de succès | Rollback |
|---|---|---|---|---|
| **T0** | **Mode ombre** : pipeline complet calculé et publié en capteurs HA (`TWC Synth Shadow L1-3`), la borne reste en RAW | rien (lecture seule) | S continu, sans NaN, |S−RAW| conforme aux étages ; rejouer une charge réelle et vérifier hors-ligne la pente α et le crossfade FF | trivial (aucun effet borne) |
| **T1** | Extrapolation + slew SEULS (α = 1, FF off, coussin 0, plancher off) — le plus proche du RAW actuel | E4+E6 | non-régression : charge démarre, polling stable, zéro trip sur 1 h ; plausibilité OK (signal plus lisse que le RAW accepté) | synth OFF |
| **T2** | **Découplage α = 0,75** (LE test critique). Provoquer marge < demande (demande 16 A, maison chargée) et observer 30 min | E2 (+T1) | modulation continue SOUS la consigne, oscillation résiduelle bornée (< ±3 A), **zéro ouverture de contacteur**, polling jamais interrompu ; échec = borne ignore le signal ou trips → noter, synth OFF, analyser | synth OFF (retour RAW < 1 s) |
| **T3** | Coussin + plancher + budget J (STGE garde active) | E5 | marge présentée jamais < 6,5 A ; simuler une montée maison (bouilloire) : descente douce, pas de coupure ; vérifier J qui s'intègre et se purge ; vérifier pause biais plein → arrêt franc (I3) | numbers à 0 / synth OFF |
| **T4** | Feed-forward : allumer pompe piscine puis une clim PENDANT une charge, avec puis sans FF | E3 | overshoot pire phase réduit (mesurer avant/après), crossfade sans double marche, TTL purge une injection fantôme (débrancher l'équipement au disjoncteur pour simuler) | FF off |
| **T5** | **Soak 24 h** Whale + une session invitée réelle, tous étages ON, contrôleur Fleet toujours actif par-dessus | tout | zéro coupure DPM, zéro alerte borne, compteurs de vie stables, aucune intervention pause binaire hors vraie saturation | synth OFF |
| **T6** | Décision de rétrogradation du contrôleur Fleet (gestionnaire de session) + généralisation invités | config HA | — | réactiver le contrôleur |

Chaque T donne lieu à une entrée dans la doc LOGIQUE (leçons numérotées) et
un backup daté du YAML avant flash (convention existante). Jamais de flash
pendant une charge (règle 2.8). QA de latence rejouée comme au lot UDP
(WS `subscribe_entities`, critère médiane ≤ 1,5 s inchangé).

---

## 11. Estimation d'effort

| Lot | Contenu | Volume | Sessions |
|---|---|---|---|
| S1 | E2 découplage + estimateur Î + observabilité ombre (T0) | ~120 l. ESP + 3 capteurs | 1 |
| S2 | E4+E6 (extrapolation, slew) + T1 | ~60 l. ESP | 0,5 |
| S3 | T2 (campagne de mesure, la valeur est dans le test) | protocole + analyse WS | 1 |
| S4 | E5 gouverneur (coussin, plancher, budget J, STGE) + T3 | ~90 l. ESP + 4 numbers | 1 |
| S5 | E3 feed-forward (ESP ~70 l. + package HA ~150 l.) + T4 | ~220 l. | 1 |
| S6 | T5 soak + doc (LOGIQUE, 20_FIRMWARE §2.10, mémoire) + décision T6 | doc | 0,5-1 |

**Total : ~5-6 sessions de travail, ~450 lignes ESP + ~200 lignes HA.**
Aucun matériel à acheter (verdict 40_ : les pinces sub-seconde n'apportent
rien — le synthétiseur travaille la FORME du signal, pas sa fraîcheur).
Point d'arrêt naturel après S3 : si T2 échoue, S4-S5 gardent de la valeur
réduite (coussin/FF sur signal à gain 1 adoucissent quand même les montées
maison) mais l'ambition « plus jamais de coupure DPM » retombe sur la
variante V1 (gain constant PVi1) ou le statu quo binaire.

---

## 12. Variantes comparées (synthèse de décision)

| Variante | Principe | Stabilité | Marge perdue | Plausibilité | Verdict |
|---|---|---|---|---|---|
| V0 statu quo | RAW + pause binaire | boucle gain 1 : bang-bang si contrainte | 0 | prouvée | baseline — coupures franches inévitables en zone contrainte |
| V1 PVi1 littéral | `reported = f(avail)`, gain k constant | prouvée terrain (k = 0,75) | `E/(1+k)` ≈ 43 % de la marge dynamique | prouvée (FVE) | repli robuste si T2 échoue |
| V2 **synthétiseur** (recommandée) | découplage AC α + FF + extrapolation + coussin/plancher + slew | −α prouvé (V1) + AC à démontrer (T2) | ~0 en régime établi | α : précédent fort ; AC : à tester | **GO par étapes** |
| V3 maison seule (α = 0) | découplage total | boucle ouverte | 0 | risque maximal (aucune corrélation) | rejetée (§4.1) |

---

*Étude rédigée le 14/08/2026 (agent architecte). Aucun fichier vivant
modifié. Prochain pas si Vincent valide : lot S1 (mode ombre, zéro risque).*

---

## ÉPILOGUE (17/08) — l'étude E2 est close : impasse instructive

L'architecture recommandée par cette étude (E2, découplage AC de la
voiture via un estimateur Î) a été implémentée, testée en réel sur
plusieurs nuits, corrigée six fois — et **abandonnée le 17/08** au profit
d'un bloc memoryless de type PVi1 (« BLOC PVi1-GRADE (17/08) » dans
`kc868-a6-1.yaml`), validé en réel le jour même. Ce qui suit consigne
pourquoi, car l'échec est plus instructif que bien des réussites.

### Les six échecs, en une table

Motif structurel (analyse croisée du 17/08) : **chaque correctif a ajouté
de l'ÉTAT INTERNE, et chaque échec suivant est un mode transitoire de
l'état ajouté par le correctif précédent.**

| Itération | État ajouté | Échec révélé (MESURÉ) |
|---|---|---|
| RAW (baseline) | — | bang-bang gain 1 (théoriquement prévu §1.2) |
| Biais rampé | rampe | fenêtre « code 10 » de 160 s |
| E2, α + EMA 60 s | EMA, Î | dither de fraîcheur, fantôme +7,7 A, trips |
| EMA 300 s | constante τ | rien changé (erreur du facteur 2π, reconnue) |
| E6 offset rampé | offset ×3 | yoyo du 17/08 00:40 (correction corrélée retardée) |
| Max-symétrique (sur E2) | maison_max | spike pub−Î pendant les transitoires |
| v2 gel + ancrage + clamp doux | gel ×3, calm ×3, eps, soupape | effondrement du publié à 11,5 A pendant un rebond ; abandon véhicule |

Décompte final : le bloc v2 portait **~20 globals de contrôle dynamique** ;
le firmware PVi1 de référence en porte UN (le timer d'escalade 120 s).

### La racine commune : l'estimateur lui-même

Toute la classe de défauts (fraîcheur, gel, purge, spike pub−Î, ancrage,
warm-up des EMA après reboot) existe parce qu'on essayait de séparer
« maison » et « voiture » avec des vitals en retard de ~2 s, face à une
borne qui décide en ~200 ms et un véhicule qui rampe à ~1 A/s. PVi1 n'a
aucun estimateur : sa mesure inclut la borne et il ne la soustrait
jamais — il n'a donc structurellement aucun de ces bugs.

**Le bug de fraîcheur par déduplication (découverte forensique du
17/08, MESURÉ au dixième d'ampère)** — l'exemple le plus parlant : la
garde de péremption d'Î (10 s) déclarait « mort » un courant voiture
parfaitement STABLE, parce que le heartbeat `force_update: true` ajouté
côté HA **n'atteint JAMAIS le nœud** — l'intégration API native ESPHome
**déduplique les états à valeur identique** avant transmission. Tout
plateau stable ≥ 10 s — l'objectif même d'une régulation — basculait Î
sur une EMA froide (~2,5 A après le reboot OTA), faisant chuter le publié
de −7,3 A à entrées physiques constantes. Preuve en trois indices
indépendants : chutes à +10,0 s pile du dernier *changement de valeur*
sur L2 et L3, et L1 immunisé par un dither accidentel (13,0↔13,1).
Corollaire mesuré le même matin : le « trip » final n'en était pas un —
c'était la **voiture qui abandonnait** après sa 3ᵉ session perturbée
(evse 9, zéro alerte borne, compteur cycles-en-charge figé — voir
`40_LOI_DE_COMMANDE.md` §4).

### La validation inverse : le memoryless gagne

Le test du 17/08 11:21-11:35 (`40_LOI_DE_COMMANDE.md` §7) a montré le
bloc PVi1-grade — pire-phase symétrique, clamp ≤ 21, zéro estimateur,
un seul timer — absorber deux échelons de charge réels (clim, pompe
piscine) en modulation douce avec paliers tenus, remontée autonome
~1 A/30 s et **zéro événement contacteur**. La question T2 de cette étude
(« la plausibilité accepte-t-elle le couplage AC ? ») n'a plus d'objet :
la publication 1:1 clampée la satisfait par construction. Le verdict
« plafond du firmware » de `40_LOI` §5 est re-scopé au passage : le
plafond était celui du gain de boucle 1, pas du firmware.

### Statut des résultats

Les « résultats négatifs » de cette étude restent **publiables tels
quels** dans LoadPilot : la caractérisation du DPM 26.18 (service
symétrique / protection pire-phase / plausibilité 1:1), la table des six
échecs, le piège de déduplication API native ESPHome et la loi « chaque
état interne ajouté crée son bug » constituent, à notre connaissance, le
corpus le plus complet existant sur ce firmware. Ce document est conservé
intégralement comme trace du raisonnement ; seule sa recommandation
(V2, E2) est caduque — la variante gagnante est une V1 durcie
(max-symétrique + clamp + escalade), plus simple que tout ce que la
table §12 envisageait.

*Épilogue rédigé le 17/08/2026 (agent documentation), sur la base des
verdicts des deux trancheurs (recorder interne 13→17/08 ; sources
externes PVi1/communauté), du forensique ACTIF-MAX v2 et du test de
validation 11:21-11:35.*
