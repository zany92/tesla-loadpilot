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
> (EN/FR, arbres de clés identiques). Le TODO const.py « parcours 5
> étapes » est levé : ✅ implémenté par la passe correctifs du 17/08 soir
> (détail en fin de section MINEURS) ; restent les demandes
> `paused`/`charger_current` et les sélecteurs de devices ESPHome
> (UX_COPY.md §Demandes, post-v0.1.0).
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

## MINEURS - statuts après la passe correctifs du 17/08 soir (n°2)

1. ✅ **corrigé** - « Signal Mode » + « Shadow Published Current » ratifiés
   dans CONTRACTS.md (table « Ajout ratifié le 17/08 soir (n°2, passe
   QA) »), avec la sémantique d'Escalation Active associée (cf. 8).
2. ✅ **corrigé (implémenté)** - `ISSUE_CHARGER_NODE_MISSING` levé par le
   coordinator quand AUCUNE entité trackée du nœud borne n'existe dans la
   machine d'états (≠ unavailable : nœud renommé/supprimé/jamais adopté),
   severity ERROR, fixable (acquittement), placeholder `{charger_node}`,
   traductions EN/FR ajoutées ; docstring `repairs.py` à jour.
3. ✅ **corrigé** - `OWNER_TBD` → `zany92`
   (github.com/zany92/tesla-loadpilot) dans README, manifest.json (×3,
   codeowners inclus), coordinator, les 2 exemples ESPHome et
   `.github/ISSUE_TEMPLATE/config.yml` ; note CONTRACTS.md §1.4 mise à
   jour. Les mentions restantes (QA_REPORT, TESTPLAN) sont des
   méta-références au critère de test, voulues.
4. ✅ **corrigé** - miroir désactivable : `_mirror_schema` passe en
   `vol.Optional` + `description={"suggested_value": …}` (jamais Required
   avec default) ; un champ vidé est absent de `user_input` et l'options
   flow reconstruit le mapping depuis la soumission → retrait effectif.
5. ✅ **corrigé** - tests d'existence des nœuds à l'étape `nodes` du
   nouveau parcours : scan de préfixe `slugify(node)_` sur les object_id
   de la machine d'états ; erreurs `charger_not_found` / `meter_not_found`
   (textes UX_COPY §1.6, EN/FR), bloquantes conformément à UX.md §2.2.
6. ✅ **corrigé** - `esphome/packages/README.md` reformulé : les deux YAML
   historiques n'étaient que PARTIELLEMENT assainis (clé UDP XXTEA en
   clair, cf. B1 - réécriture d'historique + rotation restent dues) ;
   toute extraction est à traiter comme non assainie par défaut.
7. ✅ **corrigé (partiel, assumé)** - exemple mono créé :
   `esphome/examples/charger-mono-exemple.yaml` (dérivé du tri,
   `phase_count: "1"`, miroir L1 seul) ; README des exemples réaligné sur
   les noms de fichiers réels. Pas d'exemple S3 (carte draft non testée -
   assumé pour 0.1).
8. ✅ **corrigé (sémantique)** - `escalation_state = esc && law_active`
   dans `twc-core.yaml` : « Escalation Active » n'est ON que si le
   plancher L+0,1 est PUBLIÉ (ACTIF-MAX). En RAW/OMBRE-MAX l'effet reste
   visible sur Shadow Published Current ; le drapeau (donc l'état
   `escalating` de l'intégration et les bannières dashboards) reste OFF.
   Ratifié dans CONTRACTS.md.
9. ➖ **sans objet** - jugé acceptable par la QA, aucun changement.
10. ✅ **documenté (limite assumée)** - gauges à `max: 20` avec consigne
    d'ajustement ; la carte gauge du cœur HA n'accepte qu'un nombre
    STATIQUE pour `max` (pas d'entité/template sans carte HACS, exclue par
    le contrat « core cards only ») → limite documentée en tête de
    `loadpilot-overview.yaml`.

### Complément passe correctifs - parcours config-flow 5 étapes (TODO M4)

✅ **implémenté** : `user` (profil compteur) → `nodes` (2 boîtiers,
existence vérifiée) → `electrical` (type d'installation + presets kVA +
limite/buffer ; validations `budget_too_small`/`tri_limit_suspicious`
inchangées) → `mirror` (L1 seul en mono) → `confirm` (récapitulatif via
placeholders, création de l'entrée). Traductions EN/FR restructurées
(étapes `nodes`/`electrical`/`confirm`, arbres de clés identiques,
101 feuilles).

Arbitrages pris :
- récap `confirm` : les placeholders HA ne varient pas selon la langue →
  `{country_profile}` passé en libellé quasi neutre (« France - Linky
  (TIC) », « DSMR P1 »…) et `{phases}` en chiffre (« {phases}-phase » /
  « {phases} phase(s) ») - légère déviation du copy UX_COPY §1.5 ;
- l'étape `electrical` montre la liste COMPLÈTE des presets mono+tri (le
  type d'installation se choisit sur le même écran, comme la maquette
  UX.md §2.3) ; l'options flow, lui, filtre selon les phases de l'entrée ;
- erreurs nœud introuvable BLOQUANTES (choix UX.md §2.2 : « le boîtier
  doit être adopté … avant cette étape ») ;
- options flow maintenu en UNE étape `init` (UX_COPY §2 en décrit deux -
  hors périmètre de la passe, comportement inchangé par ailleurs).

Validations passe correctifs : py_compile 8/8 OK ; json.load 4/4 OK ;
arbres de clés EN/FR identiques (101 feuilles) + placeholders `{x}`
identiques clé à clé ; yaml safe_load OK (twc-core, exemples borne tri et
mono, les 2 dashboards).

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


> Note (17/08 soir) : B1 est TRAITÉ depuis le 17/08 après-midi (historique git recréé sans la clé, force-push, clé XXTEA tournée en prod sur les deux nœuds). Le rappel « reste dû » plus haut est obsolète.

> Note (17/08 nuit) : couche de mapping d'entités ajoutée. `entry.options["entity_overrides"]` remappe chaque clé de `CHARGER_TRACKED_ENTITIES` vers un entity_id complet (clé absente = défaut générique, valeur null/"" = entité déclarée absente, tolérée) ; le failsafe ne dépend plus que des 6 mesures essentielles (`ESSENTIAL_KEYS`). Étape d'options « advanced_mapping » (opt-in par case à cocher) + traductions EN/FR ; py_compile OK, arbres de clés EN/FR identiques.
