# Tesla LoadPilot — Plan de test avant publication

> Propriété QA. Campagne à dérouler AVANT le premier tag public `v0.1.0`.
> Trois volets : (A) non-régression sur le site pilote (déjà en prod),
> (B) installation from-scratch depuis le repo, (C) cas limites / pannes.
> Chaque cas indique : préparation, action, attendu, critère d'échec.
> Rappel sécurité : toute intervention RS485/TIC se fait disjoncteur coupé
> (voir `INSTALL_FR.md` §0). Ne jamais flasher le nœud borne pendant une
> charge.

## 0. Pré-requis de la campagne

- [ ] `esphome config` puis `esphome compile` passent sur :
  - `examples/charger-kc868-a6.yaml` (avec un `secrets.yaml` local et les
    packages consommés en CHEMIN LOCAL, le tag n'existant pas encore) ;
  - `examples/meter-teleinfo-olimex-poe.yaml` ;
  - les squelettes `dsmr-p1` / `sml-de` / `ct-clamps` : **config seule**
    (ils sont marqués jamais compilés — l'objectif est zéro erreur de
    syntaxe/schéma, pas une validation fonctionnelle).
- [ ] `python -m script.hassfest` (ou l'action GitHub hassfest) passe sur
  `custom_components/loadpilot`.
- [ ] Validation HACS (action `hacs/action`) passe.
- [ ] Le scan secrets de la QA est vert **y compris sur l'historique git**
  (voir QA_REPORT.md — bloquant B1 : réécrire l'historique et/ou tourner la
  clé UDP avant tout push).

## A. Site pilote (prod Loupiac) — non-régression de l'extraction

Le site tourne aujourd'hui sur `kc868-a6-1.yaml` (bloc PVi1-GRADE 17/08).
Objectif : prouver que `twc-core.yaml` + `boards/kc868-a6.yaml` +
`providers/teleinfo-fr.yaml` reproduisent EXACTEMENT le comportement validé.

| # | Test | Attendu | Échec si |
|---|---|---|---|
| A1 | Flasher le nœud compteur avec `teleinfo-fr.yaml` (hors charge) | UDP Age < 1100 ms côté borne, courants sub-ampère cohérents avec le Linky (±0,1 A) | perte de trames, cadence > 2 s |
| A2 | Flasher le nœud borne avec le core extrait (hors charge) | Polling Active ON, Poll Interval 190–200 ms stable ≥ 1 h | trou de polling > 2 s, retry storm |
| A3 | Vérifier les entity_id contractuels (§3.1/§3.2 CONTRACTS.md) dans HA | les 15 entités borne + 6+1 compteur existent sous les noms exacts | tout écart de nom (les dashboards/l'intégration cassent) |
| A4 | Mode `OMBRE-MAX` pendant une charge réelle ≥ 30 min | Shadow ≤ L en permanence ; publié = mesure brute + biais | shadow > L, NaN, zéro transitoire |
| A5 | Bascule `ACTIF-MAX` pendant charge, maison chargée (four/PAC) | modulation douce, paliers tenus, remontée ~1 A/30 s, **zéro cycle contacteur** (compteur lifetime avant/après) | tout événement contacteur, oscillation entretenue |
| A6 | Échelon de charge (déclencher PAC/piscine pendant charge) | absorption sans dépassement du contrat au-delà du buffer, pire phase respectée | dépassement soutenu > budget |
| A7 | Escalade : forcer dispo nulle 120 s (baisser Contract Limit) | à 120 s : publication L+0,1, arrêt propre, `Escalation Active` ON, état HA `escalating` | arrêt avant 120 s, pas d'arrêt, claquement contacteur |
| A8 | Biais : `loadpilot.set_bias 6` pendant charge puis `resume` | descente à 0,5 A/5 s, remontée 1 A/5 s (Bias Applied suit en rampe) | saut non rampé pendant charge |
| A9 | Biais contacteur ouvert (pas de véhicule) | cible appliquée IMMÉDIATEMENT (pas de fenêtre « code 10 ») | rampe appliquée à vide |
| A10 | Kill-switch OFF pendant 10 min | publication 0 A constante, la borne retombe au comportement d'usine (curseur appli), état HA `off` | la borne reste bridée |
| A11 | 24 h en `ACTIF-MAX` (usage normal) | zéro reboot nœud, zéro cycle contacteur, UDP Age p99 < 2 s | reboot spontané, watchdog |

## B. Installation from-scratch (répétition de l'expérience utilisateur)

Sur une instance HA VIERGE (VM) + les deux ESP32 de rechange si possible :

| # | Test | Attendu |
|---|---|---|
| B1 | Suivre README quick start mot à mot (HACS custom repo + intégration) | l'intégration s'installe, le config flow se lance sans lire d'autre doc |
| B2 | Config flow 3 étapes, valeurs par défaut | entrée créée, `sensor.loadpilot_state` existe ; état `failsafe` tant que le nœud borne est absent (vérité sûre) |
| B3 | Config flow avec nom de nœud personnalisé (`ma-borne`) | les entités trackées suivent le slug ; documenter que les dashboards livrés supposent les noms par défaut |
| B4 | Config flow monophasé (`phases: 1`) | seuls `headroom_l1`/L1 existent ; pas de warnings L2/L3 dans l'intégration (les warnings ESPHome côté miroir sont documentés bénins) |
| B5 | Options flow : changer limite 21,7 → 30 A, buffer 10 → 15 % | reload, knobs poussés vers le nœud (numbers du nœud mis à jour), `budget_a` recalculé |
| B6 | Services : `set_bias` 3,3 A (pas invalide) | erreur de validation propre, pas de stack trace |
| B7 | `loadpilot.pause` / `resume` sans entrée chargée | erreur HA lisible « No LoadPilot config entry is loaded » |
| B8 | Importer `dashboards/loadpilot-overview.yaml` et `loadpilot_card.yaml` | zéro carte en erreur avec les noms de nœuds par défaut (hors carte SoC commentée) |
| B9 | Suivre INSTALL_FR sur le matériel de rechange (TIC + RS485) | le guide suffit ; noter chaque écart guide/réalité en issue |
| B10 | Traductions : dérouler le config flow en FR puis en EN | aucun `[UX_COPY.md pending]` visible dans la release finale ; **vérifier les entity_id générés sur une instance FR** (piège : nom d'entité traduit → entity_id différent du contrat) |
| B11 | Repair skew : flasher le nœud avec `loadpilot_fw_version: "0.0.9"` | issue « version skew » levée avec les deux versions, effacée après correction |

## C. Cas limites et pannes (matrice ARCHITECTURE.md D2)

| # | Scénario | Action | Attendu | Critère d'échec |
|---|---|---|---|---|
| C1 | Perte UDP seule | débrancher l'Ethernet du nœud compteur | à 5 s : Source `UDP`→`HA` (miroir), régulation continue avec latence dégradée | trou de régulation, fail-safe prématuré |
| C2 | Perte UDP + miroir (HA up, entités mortes) | stopper le nœud compteur (les entités miroir passent unavailable) | à ~5+10 s (debounce) : `FAILSAFE`, publication main_breaker, charge bloquée, issue Repair levée | charge qui continue sur mesure gelée |
| C3 | Perte HA seule, UDP frais | arrêter Home Assistant pendant une charge régulée | la régulation CONTINUE (Source `UDP`), aucune perturbation ≥ 30 min | reboot du nœud (reboot_timeout ≠ 0), bascule intempestive |
| C4 | Perte HA + UDP (double panne) | HA arrêté puis nœud compteur coupé | `FAILSAFE` : charge bloquée, JAMAIS de charge non contrôlée | toute charge > 0 A en double panne |
| C5 | Retour de source | rebrancher le compteur après C2/C4 | reprise `UDP` < 5 s, reprise de charge sans intervention, issue Repair effacée | reprise manuelle nécessaire |
| C6 | **TIC gelé, nœud vivant** (hat débranché, ESP32 up) | débrancher le hat téléinfo seulement | ATTENDU CONTRACTUEL : silence UDP (« jamais répéter une valeur figée », docs/15 §1) → bascule HA/failsafe. **À VÉRIFIER : packet_transport peut réémettre le dernier état à 1 Hz** — si les valeurs gelées continuent d'être diffusées, c'est une violation du contrat à corriger avant tag | la borne régule sur une mesure figée |
| C7 | Reboot nœud borne pendant charge | couper/rétablir l'alim du KC868-A6 en charge | au boot : publication main_breaker (charge bloquée) jusqu'à la première mesure, puis reprise ; mode restauré `ACTIF-MAX` ; Contract Limit/Buffer restaurés flash ; Bias Target = 0 | boot en pleine marge (charge non contrôlée), knobs perdus |
| C8 | Reboot nœud compteur | couper/rétablir l'Olimex | C1 puis C5 enchaînés ; rolling code accepté après reboot (pas de rejet permanent) | paquets rejetés en boucle après reboot |
| C9 | Coupure secteur complète puis retour | tout couper 2 min | les deux nœuds reviennent seuls, régulation rétablie sans HA (si HA plus lent) | ordre de boot bloquant |
| C10 | Monophasé | banc mono (`phase_count: "1"`, provider B/C=0) | loi dégénérée sur L1 seule, miroir L1 suffisant, pas de fail-safe cause B/C | fail-safe déclenché par les phases absentes |
| C11 | Véhicule : abandon silencieux | 3+ interruptions de charge rapprochées | comportement documenté (INSTALL_FR §7) : le véhicule peut abandonner — vérifier que la doc suffit au diagnostic | non documenté / diagnostic impossible |
| C12 | Paquet UDP forgé/rejoué (XXTEA + rolling code) | rejouer un paquet capturé | paquet rejeté (log warning), aucune influence sur la publication | mesure falsifiée acceptée |
| C13 | Deux destinations UDP (broadcast + unicast) | configurer les deux | rejet du doublon documenté (warning/s) — vérifier l'absence d'effet sur la fraîcheur | fraîcheur cassée par les doublons |

## D. Critères GO / NO-GO de publication

GO uniquement si TOUT est vrai :

1. **Secrets** : historique git réécrit sans la clé UDP Loupiac OU clé
   tournée en prod ET historique réécrit (les deux recommandé) ; scan
   secrets vert sur TOUTES les révisions publiées.
2. A1–A11 verts sur le site pilote (dont 24 h A11 sans événement).
3. C1–C9 verts ; C6 tranché (silence prouvé ou correction implémentée).
4. B1–B8 verts sur instance vierge ; B10 tranché (entity_id stables en FR).
5. hassfest + validation HACS verts ; `esphome config` vert sur les 2
   exemples et les 4 providers.
6. Zéro `[UX_COPY.md pending]` dans translations/ ; zéro `OWNER_TBD`
   (compte de publication tranché) ; LICENSE définitive posée (accord PVi1
   obtenu — sinon le repo reste privé, cf. LICENSE.placeholder).
7. Divergences contrat/UX arbitrées (buffer 30 vs 50 %, limite 6–120 vs
   10–100 A, état `paused`, capteur courant véhicule) — voir QA_REPORT.md.
8. README/INSTALL relus après extraction : plus aucune affirmation basée
   sur l'ancien firmware de référence (mode au boot, capteurs Shadow ×3,
   « Linky Source Active »).

NO-GO immédiat si : un seul cas C4/C6/C7 échoue (sécurité), ou un secret
subsiste dans l'historique.
