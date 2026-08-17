# DESIGN — Loi de publication pire-phase TOUJOURS CO-VARIANTE (flash n° 2)

> **IMPLÉMENTÉ le 17/08 soir (flash n° 2) — VALIDÉ EN RÉEL le soir même**
> (19:06-19:43) : danse d'équilibre ±1 A à la frontière du budget (régime
> normal, pas une défiance), descente continue 16→12+ A sous échelon
> +4 clims (pente publiée L+0,95), cascade complète
> descente→pause→relâche→reprise autonome de session. Le plan d'ombre §6
> a été court-circuité par la validation directe. Voir `BEHAVIOR.md` §8
> (« Evening validation ») et TESTPLAN §A (relevé 17/08). Porté dans le
> firmware générique `esphome/packages/twc-core.yaml` (numbers « Law Echo
> Gain » 0,5 / « Law Max Excursion » 1,0). Le texte ci-dessous est
> conservé tel quel (état d'esprit AVANT flash).
>
> ~~**Statut : DESIGN, rien n'est flashé.**~~ Préparait le flash n° 2 du nœud
> `kc868-a6-1` (ESPHome 2026.7.4). Remplace le cœur du bloc
> « PVi1-GRADE v1.1 » (lambda `recompute_ct`,
> `/config/esphome/kc868-a6-1.yaml` l. ~1382-1442) : le clamp ≤ 21 +
> dither ±0,05 + escalade 120 s + switch STOP.
>
> Sources : leçons 29-30 (`contrat_electrique_LOGIQUE.md`),
> `BEHAVIOR.md` §4 (état de défiance), micro-lois communautaires
> (fil HA 985613 ; TWCManager issue #20, utilisateur *olaliv*, mono
> ~26.2 ; *tomiczech* ; PVi1). Aucun secret ici.

## 1. Le problème à résoudre (mesuré)

Le clamp v1.1 rend le trip impossible (`pub ≤ 21` toujours) mais **fige le
publié en saturation** : pendant une rampe voiture 8→16 A sous clamp, le
publié n'a bougé que de +0,7 A — huit ampères du courant propre de la borne
sans écho dans le compteur qu'elle polle. Le contrôle de corrélation du
firmware 26.x casse → **défiance de session latchée** : plus de service,
plus de morsures, plus d'intégrale, escalade 21,1 ignorée 8 min. Le clamp
qui protège du trip est précisément ce qui fabrique le compteur menteur
(leçon 30, BEHAVIOR.md §4, corroboré par PVi1, Klangen82 #1/#7).

**Invariant à garantir désormais** : le publié n'est JAMAIS une valeur
morte, et l'écho des variations réelles (surtout la composante borne) est
TOUJOURS présent — y compris en contrainte.

## 2. Micro-lois d'appui (RAPPORTÉ, à recalibrer chez nous)

Fil HA 985613 + TWCManager #20 (olaliv, mono ~26.2) et tomiczech :

| Publié (vs limite L) | Réaction borne |
|---|---|
| L + 0,1 | descente ~1 A/s |
| L exactement | tient le palier |
| L − 0,1 | remontée lente |
| > L − 5 au démarrage | **session refusée** (il faut ≥ 5 A de marge affichée pour démarrer) |

- Nudges gagnants (olaliv) : **±1 A max autour de la limite, un cycle sur
  deux** — le reste du temps on publie la réalité corrélée.
- tomiczech : impulsions d'un seul cycle, +1 A pour réduire / −1,2 A pour
  augmenter, « every fifth request ». À ~190 ms/poll, un cycle sur cinq
  ≈ 1 Hz — exactement la cadence de notre `recompute_ct` : notre grain de
  publication est déjà le bon.
- PVi1 : jamais de dilution (EMA/moyenne = rejet en secondes), mais **un
  gain multiplicatif sans retard est accepté** ; preuve terrain qu'un
  signal à gain < 1 module durablement (BEHAVIOR.md §3, §9).
- La borne ne lit QUE les registres courant (olaliv) — les registres
  puissance restent publiés par cohérence (coût nul), mais la loi se
  raisonne en ampères.

Chez nous : tri, L = 21 A, budget contrat 19,53 A (21,7 × 0,9),
polls ~190 ms, service près de la limite en 5-20 s, intégrale de
protection ~20-21 A·s au-dessus de 21 (décroissante sous la limite).

## 3. La loi candidate — « compression bornée à point fixe L »

### 3.1 Idée

Hors contrainte, on publie la **réalité décalée** telle quelle (gain 1,
zéro retard) ; en contrainte, on publie L + une image **compressée mais
strictement croissante** de l'excès, bornée à +1 A. Le publié n'est plus
jamais une constante : il monte quand la réalité monte, descend quand elle
descend, et son niveau au-dessus de L est en même temps le signal de
descente mesuré (§2). Il n'y a **aucun état nouveau** — la loi reste une
fonction pure de l'entrée du cycle, fidèle à la leçon 28 (« chaque état
ajouté crée son bug »).

Identité utile : hors clamp, la v1.1 publie déjà
`o_raw = max_p(m_p) + biais + (L − budget)` — c'est la pire phase réelle
décalée d'une constante (+1,47 A à b = 10 %, + biais). Un décalage additif
constant préserve la corrélation 1:1 (les DELTAS sont identiques) ; seule
la zone clampée était morte. La loi covariante ne change donc RIEN hors
contrainte : elle remplace uniquement le plat du clamp par une pente.

### 3.2 Pseudo-code exact (remplace le bloc `{ ... }` PVi1-GRADE)

```text
# Entrées d'un cycle recompute_ct (1 Hz + événementiel) :
#   m_p        mesures par phase, APRÈS pare-feu anti-glitch (doc jumeau)
#   bias       twc_bias_applied (rampe existante, inchangée)
#   budget     enedis_limit × (1 − b/100)          # 19,53 A à b = 10 %
#   L          twc_conductor_limit (21)
#   stop       switch twc_charge_stop
#   capped_since_ms   timer existant (seul état conservé)
# Constantes proposées :
#   K_ECHO = 0.5      # gain de compression au-dessus de L
#   E_MAX  = 1.0      # excursion max au-dessus de L
#   E_MIN  = 0.1      # plancher du nudge (signal de descente minimal)
#   DTH    = 0.05     # dither alterné 1 Hz, TOUJOURS actif

o_raw = max_p(m_p) + bias + (L − budget)     # ≡ L − av_min de v1.1, non clampé
e     = o_raw − L                            # excès vs limite publiée

si e <= 0 :                                  # HORS CONTRAINTE
    pub = o_raw                              # réalité décalée, gain 1, zéro retard
    capped_since_ms = 0
sinon :                                      # EN CONTRAINTE
    pub = L + clamp(K_ECHO * e, E_MIN, E_MAX)
    si capped_since_ms == 0 : capped_since_ms = now
    # filet d'escalade conservé (observabilité + arrêt garanti) :
    si now − capped_since_ms >= 120 s : pub = max(pub, L + E_MIN)

si stop : pub = max(pub, L + E_MIN)          # STOP direct inchangé

pub += (seconde paire ? +DTH : −DTH)         # jamais deux fois la même valeur
publier pub À L'IDENTIQUE sur les 3 voies courant, et pub×230 sur les 3
voies puissance ; sh_* = pub (ombre)
```

Différences vs v1.1, en une ligne chacune :

1. le plat `pub = L − dth` en saturation devient une **pente**
   `L + K_ECHO·e` bornée [L+0,1 ; L+1] ;
2. le dither devient symétrique ±0,05 et **permanent** (même hors
   contrainte : assurance à coût nul contre toute source momentanément
   plate) ;
3. l'escalade 120 s devient un simple **plancher** (`max(pub, L+0,1)`) —
   dès qu'il y a excès la loi publie déjà ≥ L+0,1, donc le signal de
   descente est actif dès la première seconde de contrainte au lieu
   d'attendre 120 s ; le timer reste comme filet et pour l'observabilité
   (`Escalation Active`) ;
4. rien d'autre ne bouge : sources/fail-safe, biais/rampe, STOP, modes
   RAW/OMBRE-MAX/ACTIF-MAX, boot à `main_breaker`.

### 3.3 Pourquoi ce point fixe exactement en L

Toute compression qui démarre SOUS L (soft-knee classique) retarde
l'engagement du service : la borne ne verrait la contrainte que pour un
excès réel déjà important (à genou L−1 et gain 0,25, elle n'engagerait
qu'à +3 A réels — inacceptable, le contrat serait dépassé en silence). Le
point fixe en L garantit : `réalité au budget ⇔ publié à la limite`, comme
aujourd'hui — l'engagement du service se produit exactement à la vraie
contrainte, quelle que soit la fonctionnelle exacte (symétrie conservée :
min = moy = max sur les 3 voies).

## 4. Analyse

### 4.1 Risque intégrale de protection (le prix de la co-variance)

Le trip n'est plus « impossible par construction » : le publié peut vivre
au-dessus de 21. Il devient **improbable par dynamique**, et c'est
quantifiable avec l'intégrale mesurée (~20-21 A·s, décroissante sous la
limite ; décroissance non calibrée — toutes les durées ci-dessous sont
donc des BORNES BASSES, décroissance supposée nulle) :

| Publié soutenu | Vie max avant coupure (sans décroissance) |
|---|---|
| L + 0,1 | ~200-210 s |
| L + 0,5 | ~40-42 s |
| L + 1,0 | ~20-21 s |
| L + 1,05 (E_MAX + dither) | ~19-20 s |
| impulsion isolée 1 s à +1 A | ~1 A·s → négligeable (et décroît ensuite) |

À mettre en face des dynamiques mesurées : service près de la limite en
**5-20 s** (19 s mesurés au clamp du 17/08), et à publié ≥ L+0,1 la
descente rapportée est **~1 A/s**. Scénarios :

- **Excès causé par la voiture** (elle a de la marge de baisse) : la borne
  la tire à ~1 A/s → e décroît de ~1/s → exposition au-dessus de L de
  l'ordre de quelques secondes, intégrale accumulée ~2-5 A·s ≪ 20.
  Marge de sécurité ×4 à ×10.
- **Excès maison, voiture encore modulable** : identique (la voiture est
  la seule variable d'ajustement de la borne).
- **Excès maison, voiture au plancher (~6 A, plancher régulé 5 A
  rapporté)** : e persiste → pub reste > L → la borne finit par
  s'arrêter (service) ou par couper (intégrale, ≥ 20 s à E_MAX). Un
  claquement ici est le DERNIER filet d'une vraie surcharge que ni la
  voiture ni la couche HA (pause ~40-120 s, délestage) n'ont résorbée —
  comportement acceptable et voulu. Contacteur ouvert = plus de charge à
  couper = l'excès résiduel est un problème maison, hors périmètre borne.
- **Cas pathologique** : oscillation de la maison pile autour du budget →
  entrées/sorties de contrainte répétées. Chaque excursion charge un peu
  l'intégrale ; la décroissance sous la limite la vide. Non chiffrable
  sans la constante de décroissance → c'est une mesure prioritaire du
  plan d'ombre (§6, métrique M3).

**Option « soupape intégrale » (NON recommandée au flash n° 2)** : forcer
pub = L − 0,1 pendant 5 s après 15 s continues au-dessus de L. Elle
ajoute un état-machine (le type exact d'état qui a produit les six échecs
du synthétiseur) pour couvrir un cas que le service couvre déjà avec ×2-4
de marge. À ne considérer que si l'ombre mesure des durées continues
au-dessus de L avec p99 > 12 s.

### 4.2 Démarrages de session (contrainte publié ≤ L − 5)

- En contrainte (e > 0) : pub > L > L−5 → démarrage refusé. Correct :
  pas de place.
- Hors contrainte : démarrage autorisé ssi `o_raw ≤ 16`, soit une pire
  phase réelle ≤ 16 − 1,47 − biais ≈ **14,5 A** (biais 0). Le décalage
  budget rend donc le démarrage un peu plus exigeant que la réalité brute
  — c'est le sens sûr, et cohérent avec une demande mémorisée de 16 A.
- Piège vécu à ne pas recréer : la « fenêtre code 10 » (biais en rampe de
  descente = refus 160 s). La règle contacteur-ouvert → biais immédiat
  (lot 13) reste la parade ; la loi covariante n'y touche pas.
- Risque nouveau : en conditions marginales (pire phase réelle ~14-15 A
  fluctuante), des démarrages refusés/interrompus répétés peuvent mener à
  l'**abandon silencieux du véhicule** (~3 tentatives, `evse_state` 9,
  BEHAVIOR.md §5). L'anti-cyclage est du ressort de la couche HA — à
  vérifier au plan de validation (§6, métrique M5).

### 4.3 Interaction avec le biais et l'escalade

- Le biais entre dans `o_raw` AVANT la compression : un pas de rampe
  (±0,5-1 A/5 s) se lit dans le publié comme une dérive maison lente —
  plausible pour la borne (c'est déjà le cas en v1.1 hors clamp). Sous
  contrainte, le même pas est compressé ×K_ECHO : l'effet du biais
  s'affaiblit près de la limite mais son SIGNE est conservé, et
  pousser le biais finit toujours par faire monter pub → descente. Le
  levier reste monotone — juste plus mou dans la bande [L ; L+1].
- Un biais de pause (16 A) pousse o_raw très au-delà de L+2 → pub sature
  à L+1 : arrêt par la voie service (~1 A/s), plus rapide que l'ancienne
  paire clamp+escalade. Le switch STOP reste le chemin d'arrêt franc
  explicite.
- L'escalade-plancher ne peut plus être « en retard » de 120 s sur la
  contrainte ; le timer ne sert plus qu'à l'observabilité et de filet si
  E_MIN se révélait trop faible pour arrêter.

### 4.4 Modes de défaillance

| Mode | Effet avec la loi | Parade |
|---|---|---|
| Source figée (UDP gelé, valeurs répétées) | o_raw plat → pub plat → RE-création du cas leçon 29 | Le dither permanent ±0,05 garde une valeur vivante ; la fraîcheur UDP (5 s) bascule HA puis fail-safe ; le pare-feu anti-glitch ne fige rien vers le haut. Cas C6 du TESTPLAN (TIC gelé, nœud vivant) reste LE trou à trancher côté provider |
| Mesure aberrante basse (glitch 0,6 A vécu) | publierait sous le courant propre de la borne → défiance immédiate (chemin d'entrée n° 1) | Pare-feu anti-glitch AMONT (doc jumeau) : plancher contacteur-fermé + confirmation des chutes |
| Oscillation autour de L | alternance pente-1 / pente-K au point L ; gain de boucle < 1 partout (K_ECHO ≤ 0,5 au-dessus, offset budget 1,47 A en amortisseur) | vérifier en ombre (M3) ; le bang-bang mesuré exigeait le gain 1 du RAW |
| Défiance déjà installée | la loi n'y peut rien : tout est ignoré | fenêtre de reconstruction (heures de signal honnête, §6 pré-requis) ; détecteur d'entrée/sortie de défiance déjà en place |
| K_ECHO refusé par la borne (gain jugé dilution) | perte de confiance malgré la loi | improbable (PVi1 : gain sans retard accepté, α = 0,75 prouvé en champ) ; sinon variante B (§5) |

## 5. Variantes et recommandation

| | V-A compression bornée (§3) | V-B alternance olaliv (1 s / 1 s) | V-C écho AC ancré |
|---|---|---|---|
| Principe en contrainte | pub = L + clamp(K·e, 0,1, 1) | alterne cycle « pilotage » (V-A) et cycle « vérité » clamp(o_raw, L−1, L+1) | pub = L + (o_raw − ancre), borné ±1, ancre posée à l'entrée en saturation |
| Fidélité d'écho | pente K partout dans [L ; L+1] | pente 1 un cycle sur deux (dans la bande) | pente 1 (dans la bande) |
| Intégrale | ≤ 1 A·s/s, exposition réelle en s | cycles vérité peuvent camper à L+1 → duty ~50 % mais pire amplitude | ≤ 1 A·s/s |
| État ajouté | **zéro** | zéro (parité horloge) | 1 ancre + politique de ré-ancrage (≈ EMA → retard → rejeté par PVi1) |
| Conformité leçon 28 | totale | totale | violée |
| Précédent | gain < 1 prouvé (PVi1, α 0,75) | mesuré gagnant chez olaliv (mono 26.2) | aucun |

**Recommandation : V-A au flash n° 2**, avec V-B pré-écrite (le squelette
du code est le même ; l'alternance est un `if (sec % 2)` de plus) comme
plan de repli si l'OMBRE-MAX ou les premiers créneaux ACTIF montrent que
la borne exige la pente 1. V-C est documentée pour mémoire et rejetée :
son ré-ancrage est exactement la classe d'états qui a tué six versions du
synthétiseur.

Paramètres à exposer (numbers ESP, `restore_value: false`, gardes NaN) :
`K_ECHO` (0-1, défaut 0,5), `E_MAX` (0-1,5, défaut 1,0). E_MIN et DTH en
substitutions (pas des réglages).

## 6. Plan de validation en OMBRE-MAX

Pré-requis : **confiance reconstruite** avant toute lecture — ≥ une nuit
de publication honnête (le mode actuel v1.1 hors saturation suffit), le
détecteur de défiance muet sur la fenêtre. Sans cela, tout est confondu.

Instrumentation : l'ombre calcule la loi CANDIDATE (`sh_*`) pendant que la
v1.1 continue de publier. Trace 3 s minimum (recorder), épisodes de
contrainte provoqués en journée (clim + piscine, comme la validation du
17/08).

| # | Métrique | Cible GO |
|---|---|---|
| M1 | Corrélation des deltas `Δsh` vs `Δ(pire phase réelle)` hors contrainte | identité stricte (écart = dither seul) |
| M2 | En contrainte : signe(Δsh) = signe(Δréel) à chaque échantillon ; jamais > 2 échantillons consécutifs identiques (hors dither) | 100 % ; zéro plat |
| M3 | Durées continues simulées `sh > L` et intégrale simulée Σ(sh−L)·dt par épisode | p99 durée < 12 s ; intégrale < 10 A·s/épisode |
| M4 | `sh ∈ [L+0,1 ; L+1,05]` pendant toute contrainte (jamais de plat à L, jamais > E_MAX+dither) | 100 % |
| M5 | Simulation démarrage : aux instants contacteur-ouvert→demande, compter `sh > 16` | cohérent avec la marge réelle ; pas de flapping ≤ L−5 / > L−5 en < 60 s |
| M6 | Étalonnage escalade : distribution de (temps de contrainte continue) vs les 120 s du filet | le filet ne se déclenche jamais en usage normal |

Passage en ACTIF-MAX : créneaux courts surveillés (30 min), STOP à portée,
compteur `contactor_cycles` avant/après, détecteur de défiance en alerte
temps réel, véhicule à 16 A, maison vivante — mêmes conditions que la
validation §8 du 17/08 pour comparaison directe. GO 24 h ensuite (patron
A11 du TESTPLAN). Toute entrée en défiance pendant les créneaux = STOP,
retour v1.1, analyse de trace avant nouvel essai.

## 7. Ce que cette loi ne résout PAS

- Une défiance déjà latchée (seule la reconstruction lente la lève) ;
- un provider qui répète des valeurs gelées (contrat providers, C6) ;
- l'abandon silencieux du véhicule après démarrages marginaux répétés
  (anti-cyclage couche HA) ;
- la constante de décroissance de l'intégrale reste non calibrée : les
  bornes du §4.1 sont volontairement pessimistes.
