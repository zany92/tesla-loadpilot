# QA_REPORT - revue complète avant commit (QA, 17/08/2026)

Verdict global : **PRÊT À COMMITTER en privé, PAS prêt à publier.**
Le code et les docs sont d'une cohérence remarquable (loi vérifiée ligne à
ligne contre la référence, registres Modbus identiques, contrat d'entités
respecté partout). MAIS un secret vit dans l'HISTORIQUE git : publication
interdite tant que B1 n'est pas traité.

Corrections mécaniques appliquées par la QA (triviales, sans débat) :
- `custom_components/loadpilot/manifest.json` - ordre des clés hassfest
  (domain, name, puis alphabétique) ;
- `docs/TESTPLAN.md` - créé (livrable de mission).

Validations mécaniques : **py_compile 8/8 OK ; json.load 4/4 OK ; yaml
safe_load 14/14 OK** (tags `!secret`/`!lambda` enregistrés neutres,
`.github/*.yml` inclus). Aucun fichier invalide.

---

## BLOQUANTS

### B1 - La clé UDP XXTEA de production est dans l'historique git
- Fichier : commit `bc796b4`, `esphome/kc868-a6-1.yaml:157` et
  `esphome/olimex-portail.yaml:82` :
  `encryption: "<clé-caviardée-rotation-en-cours>"`.
- Les fichiers sont supprimés du working tree (extraction terminée) mais
  `git show` les restitue : tout push public publie la clé. Le commit
  initial « YAML de référence assainis » n'était PAS assaini pour cette clé
  (le `ssid`/`password`/`api key` l'étaient, elle non).
- Correction proposée (les deux, dans l'ordre) :
  1. réécrire l'historique AVANT tout push - un seul commit existe, le plus
     simple est de recréer le commit initial sans les deux YAML historiques
     (ou avec la ligne remplacée par `!secret loadpilot_udp_key`) ;
  2. tourner la clé en production (procédure SECURITY.md - elle a été
     manipulée hors secrets.yaml, le repo a pu être cloné).
- Effet de bord positif : la réécriture évacue aussi les entity_id Loupiac
  (`olimex_portail_*`) présents dans ces mêmes blobs.

---

## MAJEURS (fond) - M1/M2/M4 corrigés le 17/08 soir ; M3 reste à trancher

### M1 - Les entity_id dérivés dépendent de la langue de l'instance HA - ✅ corrigé (17/08 soir)
> Résumé : `_attr_suggested_object_id` anglais épinglé sur les 5 capteurs
> dérivés (`loadpilot_state`, `loadpilot_headroom_l1/2/3`,
> `loadpilot_worst_phase`) dans `sensor.py` ; `has_entity_name` +
> `translation_key` conservés pour l'affichage ; cohérence vérifiée avec
> les deux dashboards (ids identiques). Reste à verrouiller par le test
> B10 du TESTPLAN sur instance FR.
- Fichiers : `custom_components/loadpilot/sensor.py:64` (`_attr_has_entity_name`
  + `translation_key`) + `translations/fr.json`.
- HA génère l'entity_id depuis le nom TRADUIT au moment de la création :
  sur une instance en français (le premier marché !), `sensor.loadpilot_state`
  peut naître `sensor.loadpilot_etat`, `worst_phase` → `pire_phase`, etc.
  Le contrat §3.3, les deux dashboards et les docs supposent les ids EN.
- Correction proposée : forcer `suggested_object_id` (ou fournir des noms
  d'entité non traduits et ne traduire que les états), puis verrouiller par
  le test B10 du TESTPLAN. Les entités ESPHome (§3.1/§3.2) ne sont pas
  touchées (noms anglais côté firmware).

### M2 - INSTALL_FR.md décrit l'ANCIEN firmware de référence, pas l'extrait - ✅ corrigé (17/08 soir)
> Résumé : §6 réécrit - le boot est bien `ACTIF-MAX` (restore, choix
> assumé site en prod) avec consigne explicite « premier geste après le
> flash = passer en RAW » pour réconcilier l'échelle de commissioning ;
> « 3 voies shadow » → capteur unique « Shadow Published Current »
> (publication symétrique) ; « Linky Source Active »/« Linky UDP Fresh »
> → « Source Active »/« UDP Fresh » (noms du package twc-core.yaml -
> la prod Loupiac garde ses anciens noms, hors sujet pour le guide).
- Fichier : `docs/INSTALL_FR.md:194` : « le sélecteur ne survit pas au
  reboot (démarrage = RAW, défaut sûr) » - FAUX pour `twc-core.yaml:544`
  (select `restore_value: true`, `initial_option: ACTIF-MAX`, choix
  argumenté du spécialiste : un site en prod doit re-réguler après coupure).
  Affirmation de sécurité désormais inversée dans un guide utilisateur.
- Idem :548 « les 3 voies shadow identiques » - il n'y a plus qu'UN capteur
  Shadow (`Shadow Published Current`) ; et :187 « Linky Source Active » -
  l'entité s'appelle `Source Active`.
- La balise `TODO-sync` du rédacteur couvre le principe, mais la phrase sur
  le boot est à corriger avant tout usage externe (elle inverse le
  comportement réel). Question de fond associée à trancher : le boot en
  `ACTIF-MAX` d'une PREMIÈRE installation contredit l'échelle de
  commissioning « jamais directement en actif » du même guide (sans danger
  électrique - la loi clampe - mais incohérent avec la doc).

### M3 - « Silence en panne » du provider TIC : non prouvé sur l'extrait
- Fichier : `esphome/packages/providers/teleinfo-fr.yaml:10-12` (l'en-tête
  promet le silence UDP si la mesure meurt) vs `packet_transport`
  `update_interval: 1s` qui réémet l'état courant des 6 capteurs.
- Si le hat TIC est débranché mais l'ESP32 vivant, packet_transport peut
  rediffuser indéfiniment les DERNIÈRES valeurs (gelées) : la borne
  croirait la source fraîche - violation du contrat docs/15 §1 (« jamais
  répéter une valeur figée ») héritée telle quelle de la prod, jamais
  testée dans ce scénario. Aucune compilation/试 n'étant permise ici, c'est
  le cas C6 du TESTPLAN : NO-GO tant qu'il n'est pas tranché (au besoin :
  invalider les capteurs en NAN via un watchdog `teleinfo` sans trame).

### M4 - Divergences UX ↔ implémentation (rendez-vous d'intégration n°1) - ✅ corrigé (17/08 soir)
> Résumé : source de vérité = firmware (buffer 0-30, limite 6-120) -
> UX.md/UX_COPY.md alignés (0-50 supprimé, erreurs *_out_of_range
> remplacées par les bornes de champ) ; validations implémentées dans
> `config_flow.py` (+ options flow) : `budget_too_small` (< 8 A bloquant)
> et `tri_limit_suspicious` (> 40 A tri, non bloquant, confirmable en
> revalidant) ; presets kVA France ajoutés (mono 6-24, tri 6-36, aide de
> saisie - stockage inchangé en A/phase) pour le profil `fr_tic` ; tous
> les `[UX_COPY.md pending]` remplacés par les textes UX_COPY réels
> (EN/FR, arbres de clés identiques). Restent en TODO explicite
> (const.py) : parcours 5 étapes (step electrical dédié, récap confirm,
> test d'existence des nœuds) + demandes `paused`/`charger_current`.
- Buffer : UX 0–50 % (`dashboards/UX.md:173`, `UX_COPY.md:116`) vs
  firmware/flow 0–30 % (`twc-core.yaml:601`, `config_flow.py:98`) - la loi
  clampe aussi à 30 (héritée prod). Trancher UNE valeur (30 recommandé) et
  aligner les textes.
- Limite contrat : UX 10–100 A vs implémentation 6–120 A ; la validation
  « budget résultant ≥ 8 A » et l'avertissement tri > 40 A (saisie en kVA
  probable) ne sont PAS implémentés dans `config_flow.py`.
- Parcours : UX spécifie 5 étapes (electrical avec presets kVA, confirm
  récapitulatif) - implémenté en 3 étapes sans presets ni confirmation.
  Les demandes UX (état `paused`, `charger_current`) sont proprement
  tracées dans UX_COPY.md §Demandes - à arbitrer avant v0.1.0.
- Textes `[UX_COPY.md pending]` dans `translations/{en,fr}.json` : connus,
  mais aucune release tant qu'ils sont visibles.

---

## MINEURS

1. `select` « Signal Mode » et capteur « Shadow Published Current »
   (`twc-core.yaml:537-551, 429-435`) : entités absentes du contrat §3.1 -
   additives, utiles (INSTALL_FR s'appuie dessus) ; à ratifier dans
   CONTRACTS.md plutôt qu'à supprimer.
2. `const.py:133` `ISSUE_CHARGER_NODE_MISSING` déclaré, jamais levé, sans
   traduction - implémenter ou retirer.
3. `coordinator.py:283` + `repairs.py` : `learn_more_url` avec `OWNER_TBD`
   (10 occurrences dans le repo) - suit la décision compte GitHub.
4. Options flow (`config_flow.py:117`) : une entité miroir déjà saisie
   devient `vol.Required` → impossible à retirer sans recréer l'entrée.
5. `config_flow.py` : aucun test d'existence du nœud (le dict `errors`
   reste vide) - l'UX promettait des erreurs guidées vers le guide firmware.
6. `esphome/packages/README.md:28-29` : « Both are already sanitised » -
   faux pour la clé UDP (cf. B1) ; reformuler après réécriture d'historique.
7. Pas d'exemple mono ni d'exemple pour la carte S3 draft dans
   `esphome/examples/` (drafts honnêtement marqués non testés, OK pour 0.1).
8. `Escalation Active` peut passer ON en mode OMBRE-MAX (escalade calculée
   dans l'ombre, `twc-core.yaml:987-1020`) - cosmétique, documenter.
9. Corpus docs : mentions « Loupiac » et un `number.whale_courant_de_recharge`
   (`docs/40_LOI_DE_COMMANDE.md:219`) - nom de village + entity_id inerte
   dans un doc de données : jugé ACCEPTABLE pour un repo public (aucune
   adresse, aucune IP, aucun nom de réseau dans les fichiers courants ;
   scan IP privées : néant).
10. Dashboards : gauges `max` câblées sur 21/25 A (à ajuster à la limite
    contrat, déjà noté par l'UX) ; carte SoC proprement commentée.

---

## CONFORMITÉS VÉRIFIÉES (pour mémoire)

- **Loi de commande** : `twc-core.yaml` vs bloc PVi1-GRADE de référence
  (`git show HEAD:esphome/kc868-a6-1.yaml`) - sémantique IDENTIQUE en
  ACTIF-MAX : clamp(budget−biais−mesure, 0, L), pire phase symétrique,
  escalade 120 s → L+0,1, fail-safe main_breaker, priorité UDP>HA>failsafe,
  rampe 1/0,5 A par 5 s + application immédiate contacteur ouvert (fenêtre
  de grâce 30 s), garde-fous NaN identiques. **Registres Modbus
  Neurio/Generac : diff = zéro octet.** Écarts documentés et légitimes :
  5 modes → 3 (indices recâblés correctement, fallback index 2 = ACTIF-MAX
  vs 0 = RAW en référence - cohérent avec le nouveau défaut), limite
  contrat substitution → number flash (contrat §3.1), miroir mono assoupli
  L1-seul, flag `escalation_state` ajouté (entité contractuelle),
  `reboot_timeout: 0s` api+wifi (D2, absent de la référence qui n'en avait
  pas besoin en LAN).
- **Mono/tri** : `phase_count` 1|3 dégénère proprement (B/C forcés à 0,
  miroir L1 seul requis, UDP exige toujours les 6 grandeurs = contrat §2).
- **Contrat d'entités** : les 15 entités §3.1, 6+1 §3.2, 5 §3.3 et les 3
  services §4 existent sous les noms exacts ; les dashboards ne référencent
  QUE des entités contractuelles (+1 SoC commentée) ; variante Mushroom
  avec les 4 actions explicites (leçon de l'incident).
- **manifest.json / hacs.json** : schémas valides (après le fix d'ordre) ;
  plancher HA 2025.12 conforme D4 ; `after_dependencies: esphome` cohérent.
- **Traductions** : arbres de clés EN/FR strictement identiques (diff = ∅) ;
  toutes les clés du config flow, options, selectors, services et issues
  couvertes.
- **README/BEHAVIOR vs corpus** : « cannot trip by construction »,
  l'escalade L+0,1, la validation 17/08, les résultats négatifs - tout est
  sourcé dans `docs/40` §§6-8 sans sur-promesse ; étiquettes
  MEASURED/INFERRED/REPORTED conservées ; non-affiliation Tesla en tête de
  README, attribution PVi1 + LucaTNT présentes (README, twc-core, docs).
- **Secrets (working tree)** : zéro clé, zéro IP privée, zéro
  entity_id Loupiac dans les fichiers courants ; `!secret` partout ;
  `secrets.yaml.example` cohérent (6 clés, toutes consommées, clé UDP
  partagée documentée - la demande du rédacteur est donc déjà satisfaite) ;
  `.gitignore` couvre `secrets.yaml` et `*.BACKUP*`.
