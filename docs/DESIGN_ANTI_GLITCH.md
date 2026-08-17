# DESIGN — Pare-feu de vraisemblance des mesures (anti-glitch, flash n° 2)

> **IMPLÉMENTÉ le 17/08 soir (flash n° 2) — déployé et ACTIF** (R1
> plancher 6 A contacteur fermé + R2 confirmation 2 échantillons des
> chutes > 5 A). Validation indirecte : soirée entière sans entrée en
> défiance ; le rejeu d'un glitch réel type 11:37 n'a pas encore été
> provoqué. Porté dans le firmware générique
> `esphome/packages/twc-core.yaml` (substitutions `vehicle_floor_a`,
> `glitch_drop_a`). Le texte ci-dessous est conservé tel quel (état
> d'esprit AVANT flash).
>
> ~~**Statut : DESIGN, rien n'est flashé.**~~ Filtre d'ENTRÉE du nœud
> `kc868-a6-1` : s'applique aux mesures par phase (`m_p`) AVANT
> `recompute_ct`, quelle que soit la source active (UDP / miroir HA).
> Ne touche ni la loi de publication ni le fail-safe.

## 1. Incident fondateur et périmètre

**17/08 11:37 (mesuré)** : un glitch a publié ~0,6 A sur une phase pendant
~2 s alors que la borne tirait elle-même 16 A. Un compteur d'arrivée ne
peut PHYSIQUEMENT jamais lire sous le courant de la propre branche de la
borne → valeur maximalement invraisemblable → **défiance latchée**
(chemin d'entrée n° 1, BEHAVIOR.md §4). Précédent cousin : le flash 0
numérique au boot d'un ESP32 (04:30) qui avait déjà produit une fausse
alerte fuite et le +2249 €/reboot de la chaîne coût élec — la maison a un
historique de glitchs « chute brutale vers 0 ».

Asymétrie fondamentale du risque :

- une **hausse** publiée en retard = sous-estimation de la conso = charge
  trop autorisée = risque contrat → les hausses passent **immédiatement** ;
- une **chute** publiée à tort = compteur menteur = défiance borne → les
  chutes brutales sont **confirmées** avant publication. La latence
  ajoutée ne s'applique QUE vers le bas, et vers le bas l'erreur
  transitoire est du côté sûr (on surestime la conso pendant 1-2 s).

## 2. Les deux règles

### R1 — Plancher physique contacteur-fermé (instantané, sans état)

Tant que le contacteur borne est FERMÉ (miroir lot 13 fiable), chaque
phase de l'arrivée porte au moins le courant de la borne, jamais moins que
le minimum véhicule (~6 A en AC tri). Donc :

```
si contacteur_fermé_fiable et m_p < FLOOR_A :   m_p := FLOOR_A
```

- `FLOOR_A = 6.0` (défaut) — le glitch à 0,6 A vécu aurait été écrêté à 6.
- Sens sûr : relever une mesure ne peut que RÉDUIRE la dispo publiée.
- **Fail-open** : miroir jamais vu / indisponible > 30 s / API décrochée →
  pas de plancher (mêmes critères de confiance que `twc_bias_step`).
- Limite assumée : ne protège pas contacteur ouvert — mais contacteur
  ouvert, une valeur basse est plausible (maison à vide) et la défiance de
  session n'est pas armable (pas de session).

### R2 — Confirmation des chutes brutales (2-3 échantillons)

Par phase, une chute de plus de `DROP_A` par rapport à la dernière valeur
PUBLIÉE est retenue jusqu'à confirmation par les échantillons suivants :

```
# État par phase (3 × {last_pub, pend_val, pend_n}) :
#   last_pub   dernière valeur transmise à recompute_ct
#   pend_val   candidat de chute en attente (NAN si aucun)
#   pend_n     nombre d'échantillons ayant confirmé le candidat

filtre(x) :                      # x = nouvel échantillon de la phase
  si x est NAN : retourner last_pub            # jamais de NAN en aval
  si x >= last_pub − DROP_A :                  # hausse, ou baisse douce
      pend_val = NAN ; pend_n = 0
      last_pub = x ; retourner x               # ZÉRO latence
  # chute brutale (> DROP_A sous la dernière valeur publiée)
  si pend_val est NAN ou x > pend_val + TOL ou x < pend_val − TOL_BAS :
      pend_val = x ; pend_n = 1                # nouveau candidat
      retourner last_pub                       # on retient (1er échantillon)
  pend_n += 1
  si pend_n >= N_CONFIRM :                     # la chute est réelle
      last_pub = min(x, pend_val)              # publier le niveau confirmé
      pend_val = NAN ; pend_n = 0
      retourner last_pub
  retourner last_pub                           # encore en attente
```

Le couple courant/puissance d'une même phase suit UNE décision : le filtre
juge sur le courant, et la puissance de la phase est retenue/relâchée avec
lui (jamais un courant retenu avec une puissance effondrée — incohérence
qui serait elle-même un signal invraisemblable).

### Valeurs par défaut proposées

| Paramètre | Défaut | Justification |
|---|---|---|
| `FLOOR_A` | 6,0 A | minimum véhicule mesuré (~6 A tri) ; le glitch vécu était à 0,6 |
| `DROP_A` | 5,0 A | un four qui s'arrête = −10 A/1 s → doit être confirmé mais passer vite ; les baisses ordinaires (< 5 A) passent sans latence |
| `N_CONFIRM` | 2 | à ~1 Hz UDP : chute réelle publiée au 2e échantillon ≈ **1-2 s** (exigence : arrêt de four −10 A réels passe en ~1-2 s) |
| `TOL` / `TOL_BAS` | 1,0 A / 3,0 A | un candidat est « confirmé » si les échantillons suivants restent dans [pend−3 ; pend+1] ; une remontée immédiate (glitch d'un échantillon) annule le candidat, une chute qui CONTINUE de plonger ré-arme le candidat au niveau le plus bas |

`N_CONFIRM = 3` (≈ 2-3 s) est l'option prudente si des glitchs de deux
échantillons consécutifs sont observés un jour ; commencer à 2.

## 3. Cas limites

| Cas | Comportement | Verdict |
|---|---|---|
| Vraie chute légitime (four −10 A en 1 s) | retenue 1 échantillon, publiée au 2e (~1-2 s). Pendant la retenue on publie l'ANCIENNE valeur (plus haute) → dispo sous-estimée 1-2 s → sûr | ✅ exigence tenue |
| Glitch 1 échantillon (0,6 A puis retour) | candidat posé puis annulé par la remontée → jamais publié | ✅ raison d'être |
| Glitch 2 s (vécu 11:37) | avec N_CONFIRM = 2, un glitch qui DURE 2 échantillons passerait R2 — mais R1 l'écrête à 6 A pendant la charge : la valeur « impossible » (sous le courant borne) ne sort jamais | ✅ défense en profondeur ; sinon N_CONFIRM = 3 |
| Escalier de délestage (−4 A, −4 A, −4 A) | chaque marche < DROP_A passe sans latence | ✅ |
| Chute qui continue de plonger (−6 puis −12) | le candidat se ré-arme au plus bas ; publication au rythme des confirmations, ~1 échantillon de retard par palier | ✅ acceptable |
| Bascule de source UDP↔HA (niveaux légèrement différents) | une bascule vers une valeur plus basse de > 5 A serait retenue 1 s — inoffensif ; PAS de remise à zéro du filtre sur bascule (un reset serait une porte à glitchs pile au moment fragile) | ✅ |
| Boot du nœud | last_pub initialisé à la première valeur vue (pas de candidat au boot) ; la sémantique boot = `main_breaker` en aval reste inchangée | ✅ |
| Fail-safe actif (aucune source saine) | le fail-safe publie `main_breaker` SANS passer par le filtre — chemin de sécurité intact | ✅ |
| Contacteur ouvert + maison réellement à 0,4 A | R1 inactive (pas de plancher), R2 ne retient que si la chute est > 5 A d'un coup ; une maison à vide stable passe telle quelle | ✅ |
| Source figée (valeurs identiques répétées) | HORS PÉRIMÈTRE : le filtre ne détecte pas le gel (c'est la fraîcheur UDP + le cas C6 provider + le dither de la loi qui couvrent) | ⚠️ documenté |

## 4. Coût en état et conformité leçon 28

9 petites variables (3 phases × {last_pub, pend_val, pend_n}) + rien dans
la loi de commande. C'est de l'état de FILTRAGE D'ENTRÉE, pas de l'état de
CONTRÔLE : il ne crée pas de dynamique propre dans la boucle (pas de
constante de temps au-delà de 2-3 échantillons, pas de mémoire longue,
purge automatique à chaque hausse). La leçon 28 visait les états de
contrôle (estimateur, gels, offsets) ; on reste dans son esprit — et le
filtre est testable exhaustivement hors ligne (table de vecteurs
échantillon → sortie attendue, à faire tourner avant flash).

## 5. Observabilité

- compteur `anti_glitch_holds` (nombre de retenues) + `anti_glitch_floor`
  (nombre d'écrêtages R1), exposés en sensors template 60 s ;
- log WARNING à chaque écrêtage R1 (c'est toujours un événement anormal)
  et à chaque candidat ANNULÉ (glitch avéré, la vraie cible du filtre) ;
  log INFO seulement pour les chutes confirmées (événement normal).
- Piège rappelé : JAMAIS de VERBOSE sur ce nœud (deadline Modbus 66 ms).
