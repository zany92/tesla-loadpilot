# SPEC - Buffer de sécurité (E5-lite) + activation T2

> Agent architecte, 16/08/2026. Lecture seule effectuée : `60_ETUDE_SYNTHETISEUR.md`,
> `/Volumes/config/esphome/kc868-a6-1.yaml` (vivant, E2 flashé en OMBRE),
> `contrat_electrique_LOGIQUE.md`, lovelace `.storage`. Destinataire : agent codeur.

## 0. État vivant (vérifié dans le YAML)

- `select twc_mode_signal` (RAW/OMBRE/ACTIF, `initial_option: RAW`, `restore_value: false`),
  lu via `active_index()` l. 1436 - la branche ACTIF (l. 1437-1443) publie `sv_*` seulement si
  `have_measure && twc_control_enabled && index == 2`.
- Bloc E2 « B1 » l. 1400-1444 dans `recompute_ct` : tourne DANS TOUS LES MODES, calcule
  `sv_x = pub_x − (1−α)(Î_x − Î_dc_x)` par phase, clamp I1 (`≥ pub_x − 4`), clamp `≥ 0`,
  stocke dans `sh_a/b/c` → capteurs `TWC Synth Shadow L1-3` (update 2 s).
- `pub_x` contient DÉJÀ le biais (l. 1392-1395) : le biais s'applique AVANT E2. Bon.
- Miroirs vitals : `iv_a/b/c` ← `sensor.twc_courant_vehicule_phase_a/b/c`, fraîcheur 10 s
  via `iv_*_last_ms` ; repli α_eff=1 implicite (Î := Î_dc si stale) - I7 respecté.
- `twc_synth_alpha` : number ESP 0,5-1,0, défaut 0,75, `restore_value: false`, garde NaN → 0,75.
- Substitutions : `twc_breaker_limit_a: 16`, `main_breaker_limit_a: 25`. **Il n'existe PAS de
  constante L = 21 A (Max Conductor Limit)** - à créer (§4).
- Entités HA préfixées `*.garage_kc868_a6_1_*` (ex. `number.garage_kc868_a6_1_twc_biais_courant`).

## 1. Formule du coussin proportionnel - analyse et DÉCISION

Sémantique demandée par Vincent : « buffer 10 % ⇒ le système n'exploite que 90 % des
ressources disponibles ». Ressources disponibles pour la voiture = `L − maison`.

### 1.1 Variante A (formule littérale proposée) - ÉCARTÉE

`S' = S_e2 + (b/100)·max(0, L − S_e2)`, soit `marge_vue = (1−b)·marge_instantanée`.

Défaut structurel découvert à la vérification : **la réserve s'évapore à l'équilibre**.
E2 publie la composante continue de la voiture 1:1 (c'est sa raison d'être, §5.2 de
l'étude : « aucune marge gaspillée »). Or le comportement mesuré de la borne est de
pousser le signal publié vers L (équilibre biais mesuré : I = 21 − X). Comme le coussin A
est proportionnel à `L − S_e2`, il tend vers 0 exactement quand la voiture a mangé toute
la marge : `S' = L ⟺ S_e2 = L ⟺ I* = L − maison`. **À l'équilibre la voiture exploite
100 % des ressources, pas 90 %** - le buffer ne fait que ralentir l'approche. En prime la
pente pendant les rampes devient `d(S')/d(I) = α·(1−b)` : à α=0,75 et b>13 %, on sort de
l'enveloppe prouvée PVi1 (≥ 0,65).

### 1.2 Variante B (RETENUE) - coussin sur la marge MAISON

```
maison_est_p = pub_p − Î_p                      # voiture entièrement retirée ; biais inclus
coussin_p    = (b/100) · max(0, L − maison_est_p)
S'_p         = S_e2_p + coussin_p               # coussin ≥ 0, toujours vers le HAUT
```

(En code : `sv_x += bfrac * max(0.0f, L − (pub_x − if_x));` - `pub_x` et `if_x` existent
déjà dans le bloc B1 ; noter que `maison_est = pub − Î` se simplifie exactement ainsi.)

Propriétés vérifiées :

- **Sémantique exacte et PERSISTANTE.** Régime établi (Î→Î_dc, S_e2→pub) :
  `S' = maison + I + b·(L − maison)` ; équilibre `S' = L` ⇒
  **`I* = (1−b)·(L − maison)`** - la voiture n'exploite jamais que (1−b) de la ressource,
  même après des heures. C'est la demande de Vincent, mot pour mot.
- **Pente conservée = α** (plausibilité 26.18) : `d(S')/d(I) = α − b·(1 − dÎ/dI) = α`
  quand vitals suivent (dÎ/dI = 1). T2 teste donc EXACTEMENT la pente 0,75 prévue par
  l'étude, quel que soit b - la variante A aurait contaminé le test. Résidu pendant le
  lag vitals (2 s) : l'erreur `e = I − Î` entre dans le coussin au poids b ≤ 0,3 →
  ondulation ≤ 0,2 A à b=10 %, transitoire, noyée dans le bruit maison (le coussin reste
  une composante « non corrélée » au sens du §5.5/§8 de l'étude).
- **I1 (jamais sous réalité − 4 A)** : coussin ≥ 0 ⇒ `S' ≥ S_e2 ≥ pub − 4`. Le clamp I1
  existant reste valide tel quel. La seule direction du coussin est la SUR-déclaration =
  sens sûr par construction.
- **Biais / arrêt franc (I3)** : le biais est dans `pub` donc dans `maison_est` → quand
  le biais monte, le coussin DIMINUE mais `S' ≥ S_e2` toujours. Démonstration :
  `marge_vue = (1−b)(L − maison − X) − I ≤ marge_RAW` pour tout X ≥ 0 - le coussin ne
  peut que RENFORCER l'effet du biais, jamais le retarder. Biais 16 → arrêt franc
  identique ou plus rapide. Aucune interaction dangereuse.
- **Bornes NaN (I9)** : b NaN ou hors [0, 30] → b := 10 (même patron que la garde alpha
  l. 1411). `if_x` déjà gardé (repli Î_dc). `max(0, …)` interdit tout coussin négatif.

### 1.3 Plancher véhicule (~6 A) - table buffer → courant max voiture

Régime établi, maison calme, phase la plus chargée, L = 21 A :
`I_max = (1−b)·(21 − maison)` ; la charge ne démarre jamais si `I_max < 6 A`.

| buffer b | I_max (maison 2 A) | I_max (maison 5 A) | maison bloquant le démarrage |
|---|---|---|---|
| 0 %  | 19,0 A (plafonné consigne) | 16,0 A | ≥ 15,0 A/phase |
| 10 % | 17,1 A | 14,4 A | ≥ 14,3 A/phase |
| 20 % | 15,2 A | 12,8 A | ≥ 13,5 A/phase |
| 30 % | 13,3 A | 11,2 A | ≥ 12,4 A/phase |

**Conclusion : dans la plage 0-30 %, le buffer seul ne peut JAMAIS empêcher le démarrage
maison calme** (il faudrait b ≈ 68 %). Le blocage n'apparaît qu'avec ≥ 12 A/phase de
maison - situation où on VEUT que la voiture attende. Bornes 0-30 validées.

## 2. Le helper - DÉCISION : number ESP (pas d'input_number HA)

**ESP `number:` template**, comme `twc_synth_alpha`. Raisons : (a) le pipeline ne doit
dépendre de HA pour AUCUN paramètre (HA down → miroir vitals meurt déjà proprement via
α_eff=1 ; un input_number mirroré ajouterait un chemin de staleness inutile) ; (b) survit
au redémarrage de HA ; (c) HA voit et pilote nativement les numbers ESP - le « miroir »
est gratuit ; (d) cohérence de patron avec alpha.

```yaml
# dans le bloc number: existant (JAMAIS une 2e clé racine number:)
  - platform: template
    id: twc_synth_buffer_pct
    name: "TWC synth buffer securite"
    icon: "mdi:shield-half-full"
    unit_of_measurement: "%"
    min_value: 0
    max_value: 30
    step: 1
    restore_value: false      # boot = défaut connu (esprit I8)
    initial_value: 10
    optimistic: true
```

Garde dans le bloc B1 : `float b = id(twc_synth_buffer_pct).state;
if (std::isnan(b) || b < 0.0f || b > 30.0f) b = 10.0f; const float bfrac = b / 100.0f;`

**Appliqué en OMBRE aussi** : l'insertion se fait dans le calcul de `sv_x` (bloc B1, qui
tourne dans tous les modes) → les shadows L1-3 montrent l'effet du buffer sans toucher la
borne = validation T0 gratuite avant T2. Aucun switch dédié : buffer à 0 = neutre.

## 3. Protocole T2 finalisé (opérateurs : coordinateur + Vincent)

### 3.1 Préconditions (toutes vérifiables avant bascule)

1. Buffer déployé, **T0 rejoué** : pendant une charge réelle en OMBRE, vérifier
   `Shadow ≈ RAW − (1−0,75)·(Î − Î_dc) + coussin`, aucun NaN, |Shadow − RAW| ≤ 4 A + coussin.
2. `input_boolean.contrat_elec_controle_borne_seul` ON (Whale = invité, zéro Fleet).
3. `input_boolean.contrat_elec_borne_mode_manuel` ON (plus AUCUNE écriture auto du biais),
   biais cible = 0, biais appliqué = 0 (les deux entités de la carte Borne).
4. Source Linky = UDP (capteur source = 1), vitals vivants (`sensor.twc_courant_vehicule_*`
   frais < 10 s), contacteur miroir cohérent, `TWC Poll Interval` ~191 ms stable.
5. Réglages : α = 0,75, buffer = 10 % (pente effective 0,75, enveloppe prouvée PVi1).
6. STGE bit 7 éteint ; pas de flash prévu ; backup YAML daté déjà fait au déploiement.
7. Charge en cours ou lançable, consigne véhicule 16 A ; **maison chargée** pour forcer la
   contrainte : viser `L − maison < 16 A` sur au moins une phase (clims phase 3 : c'est le
   scénario nominal).

### 3.2 Déroulé

1. Noter : compteur de cycles contacteur (lifetime borne), heure de début.
2. Charge établie stable en RAW (véhicule à sa consigne ou au plafond RAW).
3. Basculer `select.garage_kc868_a6_1_twc_mode_signal` → **ACTIF** (effet < 1 s).
4. Observer 10 min en régime contraint : le courant véhicule doit descendre sous la
   consigne et MODULER (suivre la marge), pas cycler.
5. **Scénario clim** : allumer une clim (≈ 700 VA, phase 3) PENDANT la charge → la
   modulation doit descendre en douceur ; l'éteindre → remontée douce. Répéter une fois.
6. Poursuivre jusqu'à 30 min cumulées en ACTIF.

### 3.3 Critères chiffrés

**Succès (tous requis)** : modulation continue TENUE SOUS la consigne en zone contrainte ;
oscillation résiduelle < ±3 A autour du point d'équilibre ; **zéro ouverture de
contacteur** (compteur lifetime inchangé) ; polling jamais interrompu (`TWC Poll
Interval` sans trou > 2 s) ; marge exploitée cohérente avec b=10 % (courant véhicule
d'équilibre ≈ 0,9·(21 − maison), ±1 A).

**Abandon immédiat (un seul suffit)** : la borne ignore le signal > 2 min (courant
véhicule ne réagit pas aux variations de marge publiée) → select RAW ; TOUTE ouverture de
contacteur (trip) → select RAW immédiat, noter l'horodatage pour analyse WS ; polling
interrompu > 30 s → RAW ; STGE bit 7 s'allume → RAW + laisser la machinerie HA agir ;
vitals stale > 60 s pendant le test → RAW (le test n'est plus celui d'α=0,75).

### 3.4 État à laisser selon verdict

- **SUCCÈS** : revenir en **OMBRE** (ACTIF permanent seulement après T3+ ; le select ne
  survit pas au reboot de toute façon - `restore_value: false`). Consigner : entrée
  datée dans `contrat_electrique_LOGIQUE.md` (T2 PASS + mesures : amplitude d'oscillation,
  équilibre, durée), note d'état dans `60_ETUDE_SYNTHETISEUR.md`, mode manuel biais OFF,
  borne_seul selon le souhait de Vincent.
- **ÉCHEC** : select RAW, mode manuel biais OFF, borne_seul restauré ; consigner le mode
  d'échec exact (ignoré / trip / polling) + traces WS ; NE PAS retenter avant analyse -
  le repli V1 (gain constant PVi1) devient l'option sur la table.

## 4. Consignes au codeur

### Périmètre ESP (`/Volumes/config/esphome/kc868-a6-1.yaml`)

1. Substitution nouvelle : `twc_conductor_limit_a: "21"` (Max Conductor Limit mesuré -
   distincte de `twc_breaker_limit_a: 16` qui est le plafond Home Load Management).
2. Number `twc_synth_buffer_pct` (§2) - **dans le bloc `number:` existant** (l. 972).
3. Bloc B1 (l. 1400-1444) : lire b avec garde NaN, puis pour chaque phase insérer
   AVANT le clamp I1 : `sv_x += bfrac * std::max(0.0f, L − (pub_x − if_x));` avec
   `const float L = ${twc_conductor_limit_a};`. Rien d'autre ne bouge : les clamps I1/≥0
   existants restent, la branche ACTIF consomme `sv_*` automatiquement.
4. Interdits reconduits : aucun calcul dans les `read_lambda` Modbus, pas de log par tick.

### Pièges de compile (saga du 15/08 - appliquer sans discuter)

- **Jamais deux clés racine identiques** (`number:`, `globals:`, `sensor:`…) : fusionner
  dans les blocs existants, sinon le YAML merge silencieusement mal ou refuse.
- `id(mon_select).state` **NE COMPILE PAS** en ESPHome 2026.7 → `active_index()` (voir
  l. 1436 pour le patron exact).
- Le dashboard ne stocke AUCUN log de build : valider d'abord par l'API addon
  (`devices/{id}/validate`), puis compiler ; ne pas diagnostiquer via l'UI.
- Spawn de compile qui meurt en < 1 s avec exit 2 → `firmware/clean` puis **restart de
  l'addon ESPHome**, ensuite recompiler.
- Cache chaud = itérations 3-4 min ; **un seul builder à la fois** (deux builders = crash
  type 22:46) ; **jamais VERBOSE**.
- **Flash uniquement hors charge** (contacteur ouvert - règle 2.8) ; backup YAML daté
  avant flash (convention existante).

### Périmètre HA

1. **Carte réglages** : `.storage/lovelace.lovelace`, vue « Contrat élec », section
   `{"type": "section", "label": "Borne (levier biais)"}` - ajouter UNE ligne :
   `{"entity": "number.garage_kc868_a6_1_twc_synth_buffer_securite", "name": "Buffer sécurité synthé (%)", "icon": "mdi:shield-half-full"}`
   (vérifier l'entity_id réel après flash - préfixe `garage_kc868_a6_1` confirmé sur les
   entités sœurs ; backup du fichier lovelace avant édition, convention
   `lovelace.lovelace.BACKUP_*`).
2. **`contrat_electrique_LOGIQUE.md`** : le doc n'a AUCUNE section synthétiseur à ce jour
   (vérifié par grep) - créer un court § « Synthétiseur (E2 + buffer) » : formule
   variante B, pourquoi la variante « marge instantanée » a été écartée (réserve qui
   s'évapore à l'équilibre), rappel « ne jamais brancher les automatisations HA sur les
   capteurs TWC Published/Shadow » (séparation des vérités, §6 de l'étude).
3. **`60_ETUDE_SYNTHETISEUR.md`** : note d'état en tête (E2 flashé OMBRE le 15/08,
   E5-lite buffer ajouté le JJ/08, formule B retenue, T2 prêt - renvoyer vers cette spec
   pour le protocole).

### Ce qui est HORS périmètre (ne pas toucher)

Rampe de biais lot 13, fusion des sources E1, fail-safe, read_lambdas, package HA
contrat élec, étages E3/E4/E5-complet/E6 (viendront après T2). Secrets WiFi : ne jamais
les citer dans un diff ou un log.
