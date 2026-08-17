# Tesla LoadPilot — UX COPY (all user-facing strings, EN + FR)

> Owned by the UX designer (/CONTRACTS.md §1.2). Consumed by the HA
> specialist to build `custom_components/loadpilot/translations/en.json`
> and `fr.json` (integration rendez-vous #1) — he integrates these strings
> verbatim, he does not invent them. Keys follow the Home Assistant
> translations JSON structure so the mapping is 1:1.
>
> Also serves as the `UX_STRINGS` deliverable requested by the mission
> (same content, contract-compliant filename).
>
> Conventions: FR uses **vouvoiement**, no jargon (« réserve de sécurité »
> for buffer, « ralentissement volontaire (biais) » for bias). EN is plain
> English. Rationale and wireframes: see `UX.md`.

---

## 1. Config flow (`config.step.*`)

### 1.1 `config.step.user` — country & meter profile

| Key | EN | FR |
|---|---|---|
| `title` | Welcome to Tesla LoadPilot | Bienvenue dans Tesla LoadPilot |
| `description` | LoadPilot adjusts your vehicle's charging so your home never exceeds your electricity contract. Everything runs locally — no cloud. First, tell us which meter your installation uses. | LoadPilot ajuste la charge de votre véhicule pour que votre maison ne dépasse jamais votre abonnement électrique. Tout fonctionne en local, sans cloud. Commencez par indiquer le compteur de votre installation. |
| `data.country_profile` | Meter profile | Profil compteur |
| `data_description.country_profile` | Profiles marked “preview” ship as firmware skeletons and have not been validated in production yet. | Les profils marqués « aperçu » sont des squelettes firmware, pas encore validés en production. |

Selector options for `country_profile` (`selector.country_profile.options.*`):

| Key | EN | FR |
|---|---|---|
| `fr_tic` | France — Linky (TIC) | France — Linky (TIC) |
| `dsmr` | Netherlands / Belgium — DSMR P1 (preview) | Pays-Bas / Belgique — DSMR P1 (aperçu) |
| `sml` | Germany / Austria — SML (preview) | Allemagne / Autriche — SML (aperçu) |
| `ct_clamps` | Universal — CT clamps (preview) | Universel — pinces ampèremétriques (aperçu) |

### 1.2 `config.step.nodes` — the two ESP32 nodes

| Key | EN | FR |
|---|---|---|
| `title` | Your two LoadPilot nodes | Vos deux boîtiers LoadPilot |
| `description` | LoadPilot relies on two small ESP32 nodes already set up with ESPHome: one next to the wall connector (it talks to it), one next to the meter (it measures). If you followed the guide without renaming, keep the suggested values. | LoadPilot repose sur deux petits boîtiers ESP32 déjà installés via ESPHome : un près de la borne (il lui parle), un près du compteur (il mesure). Si vous avez suivi le guide sans renommer, gardez les valeurs proposées. |
| `data.charger_node` | Charger node | Boîtier borne |
| `data.meter_node` | Meter node | Boîtier compteur |
| `data_description.charger_node` | ESPHome device name of the node wired to the wall connector (default: loadpilot-twc). | Nom ESPHome du boîtier relié à la borne (défaut : loadpilot-twc). |
| `data_description.meter_node` | ESPHome device name of the node reading your meter (default: loadpilot-meter). | Nom ESPHome du boîtier qui lit votre compteur (défaut : loadpilot-meter). |

### 1.3 `config.step.electrical` — contract & safety buffer

| Key | EN | FR |
|---|---|---|
| `title` | Your electricity contract | Votre abonnement électrique |
| `description` | These two settings are what keeps your main breaker happy. They are written into the charger node itself and keep working even when Home Assistant is off. | Ces deux réglages sont ce qui protège votre disjoncteur d'abonnement. Ils sont écrits dans le boîtier borne lui-même et restent actifs même si Home Assistant est éteint. |
| `data.phases` | Installation type | Type d'installation |
| `data.contract_limit_a` | Contract limit (amps per phase) | Limite d'abonnement (ampères par phase) |
| `data.buffer_pct` | Safety buffer (%) | Réserve de sécurité (%) |
| `data_description.contract_limit_a` | In France: 6 kVA single-phase = 30 A · 9 kVA = 45 A · 12 kVA = 60 A · 15 kVA = 75 A · 18 kVA = 90 A. Three-phase, per phase: 6 kVA = 10 A · 9 kVA = 15 A · 12 kVA = 20 A · 15 kVA = 25 A · 18 kVA = 30 A. | En France : 6 kVA monophasé = 30 A · 9 kVA = 45 A · 12 kVA = 60 A · 15 kVA = 75 A · 18 kVA = 90 A. En triphasé, par phase : 6 kVA = 10 A · 9 kVA = 15 A · 12 kVA = 20 A · 15 kVA = 25 A · 18 kVA = 30 A. |
| `data_description.buffer_pct` | With a 10% buffer, the car only uses 90% of your contract: the rest absorbs surges (an oven or a pump starting) without tripping the breaker. | Avec 10 % de réserve, la voiture n'exploite que 90 % de votre abonnement : le reste absorbe les à-coups (démarrage d'un four, d'une pompe) sans faire disjoncter. |

Selector options for `phases` (`selector.phases.options.*`):

| Key | EN | FR |
|---|---|---|
| `1` | Single-phase | Monophasé |
| `3` | Three-phase | Triphasé |

If the HA specialist implements the French kVA preset dropdown (recommended
for `fr_tic`, helper field only — storage stays `contract_limit_a` in amps),
options (`selector.contract_preset.options.*`):

| Key | EN | FR |
|---|---|---|
| `mono_6` | 6 kVA single-phase — 30 A | 6 kVA monophasé — 30 A |
| `mono_9` | 9 kVA single-phase — 45 A | 9 kVA monophasé — 45 A |
| `mono_12` | 12 kVA single-phase — 60 A | 12 kVA monophasé — 60 A |
| `mono_15` | 15 kVA single-phase — 75 A | 15 kVA monophasé — 75 A |
| `mono_18` | 18 kVA single-phase — 90 A | 18 kVA monophasé — 90 A |
| `tri_6` | 6 kVA three-phase — 10 A per phase | 6 kVA triphasé — 10 A par phase |
| `tri_9` | 9 kVA three-phase — 15 A per phase | 9 kVA triphasé — 15 A par phase |
| `tri_12` | 12 kVA three-phase — 20 A per phase | 12 kVA triphasé — 20 A par phase |
| `tri_15` | 15 kVA three-phase — 25 A per phase | 15 kVA triphasé — 25 A par phase |
| `tri_18` | 18 kVA three-phase — 30 A per phase | 18 kVA triphasé — 30 A par phase |
| `custom` | Other (enter the limit in amps) | Autre (saisir la limite en ampères) |

### 1.4 `config.step.mirror` — Home Assistant backup path

| Key | EN | FR |
|---|---|---|
| `title` | Backup if the direct link goes down | Secours si le lien direct est coupé |
| `description` | Normally the meter node talks directly to the charger node. If that link goes down, Home Assistant can relay the measurements as a backup. Optional but recommended. Without it, if both the direct link and Home Assistant are unavailable, charging is blocked for safety (your contract is never exceeded). | En temps normal, le boîtier compteur parle directement au boîtier borne. Si ce lien tombe, Home Assistant peut relayer les mesures en secours. Facultatif mais recommandé. Sans secours, si le lien direct ET Home Assistant sont indisponibles, la charge est bloquée par sécurité (votre abonnement n'est jamais dépassé). |
| `data.mirror_current_l1` | Current, phase 1 | Courant, phase 1 |
| `data.mirror_current_l2` | Current, phase 2 | Courant, phase 2 |
| `data.mirror_current_l3` | Current, phase 3 | Courant, phase 3 |
| `data.mirror_power_l1` | Power, phase 1 | Puissance, phase 1 |
| `data.mirror_power_l2` | Power, phase 2 | Puissance, phase 2 |
| `data.mirror_power_l3` | Power, phase 3 | Puissance, phase 3 |
| `data_description.mirror_current_l1` | Pick the entities coming from your meter node (suggested automatically when available). | Choisissez les entités issues de votre boîtier compteur (proposées automatiquement quand elles existent). |

Single-phase installs: only the two L1 fields are shown.

### 1.5 `config.step.confirm` — summary

| Key | EN | FR |
|---|---|---|
| `title` | Check before enabling | Vérifiez avant d'activer |
| `description` | Meter: {country_profile}. Installation: {phases_label}. Contract: {contract_limit_a} A per phase, {buffer_pct}% buffer — that leaves a budget of {budget_a} A per phase for the whole house, car included. These settings are written into the charger node: they stay active even when Home Assistant is off. Regulation itself is enabled from the LoadPilot card, not here. | Compteur : {country_profile}. Installation : {phases_label}. Abonnement : {contract_limit_a} A par phase, réserve {buffer_pct} % — soit un budget de {budget_a} A par phase pour toute la maison, voiture comprise. Ces réglages sont écrits dans le boîtier borne : ils restent actifs même si Home Assistant est éteint. L'activation de la régulation se fait depuis la carte LoadPilot, pas ici. |

### 1.6 Errors (`config.error.*`) and aborts (`config.abort.*`)

| Key | EN | FR |
|---|---|---|
| `error.charger_not_found` | Charger node not found. It must be adopted in ESPHome and visible in Home Assistant before this step (see the firmware guide). | Boîtier borne introuvable. Il doit être adopté dans ESPHome et visible dans Home Assistant avant cette étape (voir le guide firmware). |
| `error.meter_not_found` | Meter node not found. It must be adopted in ESPHome and visible in Home Assistant before this step (see the firmware guide). | Boîtier compteur introuvable. Il doit être adopté dans ESPHome et visible dans Home Assistant avant cette étape (voir le guide firmware). |
| `error.limit_out_of_range` | Enter a limit between 10 and 100 amps PER PHASE. Values above 100 usually mean the figure was entered in kVA or watts. | Saisissez une limite entre 10 et 100 ampères PAR PHASE. Au-delà de 100, la valeur a probablement été saisie en kVA ou en watts. |
| `error.buffer_out_of_range` | The safety buffer must be between 0 and 50%. | La réserve de sécurité doit être comprise entre 0 et 50 %. |
| `error.budget_too_small` | With these settings only {budget_a} A per phase remain for the whole house — the car will never be able to charge. Check the limit (in amps PER PHASE) and the buffer. | Avec ces réglages, il ne reste que {budget_a} A par phase pour toute la maison — la voiture ne pourra jamais charger. Vérifiez la limite (en ampères PAR PHASE) et la réserve. |
| `error.mirror_entity_invalid` | This entity does not provide a numeric measurement. Pick a current (A) or power (VA/W) sensor. | Cette entité ne fournit pas une mesure numérique. Choisissez un capteur de courant (A) ou de puissance (VA/W). |
| `abort.already_configured` | This LoadPilot charger node is already configured. | Ce boîtier borne LoadPilot est déjà configuré. |

Non-blocking warning (shown as description on re-display, three-phase +
limit > 40 A):

| Key | EN | FR |
|---|---|---|
| `warn.tri_limit_suspicious` | {contract_limit_a} A per phase on three-phase is unusually high — did you enter the three-phase total, or a single-phase figure? | {contract_limit_a} A par phase en triphasé, c'est inhabituellement élevé — auriez-vous saisi le total des 3 phases, ou une valeur monophasée ? |

---

## 2. Options flow (`options.step.*`)

### 2.1 `options.step.electrical`

| Key | EN | FR |
|---|---|---|
| `title` | Contract & safety buffer | Abonnement et réserve de sécurité |
| `description` | Changes are written straight into the charger node. To change country profile or nodes, remove and re-add the integration. | Les modifications sont écrites directement dans le boîtier borne. Pour changer de profil compteur ou de boîtiers, supprimez puis réinstallez l'intégration. |

Fields and field descriptions: identical to `config.step.electrical`
(§1.3). Errors: identical to §1.6.

### 2.2 `options.step.mirror`

Identical to `config.step.mirror` (§1.4).

---

## 3. Services (`services.yaml` + translations)

| Key | EN | FR |
|---|---|---|
| `set_bias.name` | Set charging slowdown (bias) | Régler le ralentissement de charge (biais) |
| `set_bias.description` | Deliberately slows the vehicle down by reserving amps for the rest of the house. 0 = no slowdown, 16 = charging paused. The value ramps smoothly — the ramp is handled by the charger node. | Ralentit volontairement le véhicule en réservant des ampères pour le reste de la maison. 0 = aucun ralentissement, 16 = charge en pause. La valeur est appliquée en douceur — la rampe est gérée par le boîtier borne. |
| `set_bias.fields.amps.name` | Reserved amps | Ampères réservés |
| `set_bias.fields.amps.description` | Amps taken away from the vehicle, per phase (0 to 16, step 0.5). | Ampères retirés au véhicule, par phase (0 à 16, pas de 0,5). |
| `pause.name` | Pause charging | Mettre la charge en pause |
| `pause.description` | Cleanly pauses vehicle charging by reserving the full budget (bias 16 A). The vehicle stops in about 2 minutes without error. Resume with “Resume charging”. | Met la charge du véhicule en pause proprement en réservant tout le budget (biais 16 A). Le véhicule s'arrête en 2 minutes environ, sans erreur. Reprise via « Reprendre la charge ». |
| `resume.name` | Resume charging | Reprendre la charge |
| `resume.description` | Releases the pause (bias back to 0). The vehicle resumes charging on its own within a few minutes. | Relâche la pause (biais remis à 0). Le véhicule reprend la charge de lui-même en quelques minutes. |

---

## 4. Repairs (`issues.*`)

| Key | EN | FR |
|---|---|---|
| `version_skew.title` | Firmware and integration versions differ | Versions firmware et intégration différentes |
| `version_skew.description` | The charger node runs LoadPilot firmware {fw_version} but the integration is {int_version}. Regulation keeps working, but behaviour may drift between versions. Update the ESPHome package pin (ref: v{int_version}) and reflash the node, or update the integration through HACS, so both match. | Le boîtier borne exécute le firmware LoadPilot {fw_version} mais l'intégration est en {int_version}. La régulation continue de fonctionner, mais les comportements peuvent diverger entre versions. Mettez à jour l'épingle du package ESPHome (ref: v{int_version}) et re-flashez le boîtier, ou mettez à jour l'intégration via HACS, pour aligner les deux. |
| `udp_stale.title` | Direct meter link is down | Lien direct compteur interrompu |
| `udp_stale.description` | The charger node has not received fresh measurements from the meter node for more than {age} — it is now using the Home Assistant backup path (slower, less robust). Check that the meter node is powered and on the network. | Le boîtier borne ne reçoit plus de mesures fraîches du boîtier compteur depuis plus de {age} — il utilise le secours Home Assistant (plus lent, moins robuste). Vérifiez que le boîtier compteur est alimenté et sur le réseau. |
| `mirror_stale.title` | Charging blocked: no measurement available | Charge bloquée : aucune mesure disponible |
| `mirror_stale.description` | Neither the direct meter link nor the Home Assistant backup is providing measurements. For safety, charging is blocked (your contract can never be exceeded). Check the meter node, then the backup entities in the LoadPilot options. | Ni le lien direct compteur ni le secours Home Assistant ne fournissent de mesures. Par sécurité, la charge est bloquée (votre abonnement ne peut jamais être dépassé). Vérifiez le boîtier compteur, puis les entités de secours dans les options LoadPilot. |

---

## 5. Notification templates (patterns for docs & future automations — one SITUATION notification per episode, never one per threshold crossing)

| Key | EN | FR |
|---|---|---|
| `notify.escalation_start` | Your home has exceeded its power budget for 2 minutes. Vehicle charging is being stopped cleanly to protect your contract. | Votre maison dépasse son budget électrique depuis 2 minutes. La charge du véhicule est arrêtée proprement pour protéger votre abonnement. |
| `notify.escalation_end` | Power is back within budget. Vehicle charging can resume. | La consommation est revenue dans le budget. La charge du véhicule peut reprendre. |
| `notify.source_degraded` | LoadPilot lost the direct meter link and switched to the Home Assistant backup. Charging continues, slightly less responsive. | LoadPilot a perdu le lien direct compteur et bascule sur le secours Home Assistant. La charge continue, un peu moins réactive. |
| `notify.source_restored` | Direct meter link restored. LoadPilot is back to normal operation. | Lien direct compteur rétabli. LoadPilot fonctionne de nouveau normalement. |
| `notify.failsafe` | No power measurement is available: vehicle charging is blocked for safety. Check that the meter node is powered (LoadPilot never risks tripping your contract). | Aucune mesure électrique disponible : la charge du véhicule est bloquée par sécurité. Vérifiez que le boîtier compteur est alimenté (LoadPilot ne prend jamais le risque de faire disjoncter). |
| `notify.pause_holding` | Charging stays paused: the house does not yet have room for the vehicle to come back at full demand. It will resume automatically when room is available. | La pause de charge est maintenue : la maison n'a pas encore la place pour le retour du véhicule à pleine demande. La reprise sera automatique dès que la place sera suffisante. |

---

## 6. Dashboard strings (used in `loadpilot-overview.yaml` / `loadpilot_card.yaml`; FR given for users who localise their cards)

| Key | EN | FR |
|---|---|---|
| `dash.master` | Charge regulation | Régulation de charge |
| `dash.master_confirm_off` | Turn regulation OFF? The wall connector returns to factory behaviour at FULL power — your contract is no longer protected. | Désactiver la régulation ? La borne repasse en fonctionnement d'usine à PLEINE puissance — votre abonnement n'est plus protégé. |
| `dash.master_confirm_on` | Turn regulation ON? The wall connector will follow your contract limit. | Activer la régulation ? La borne respectera la limite de votre abonnement. |
| `dash.state` | Status | État |
| `dash.headroom` | Headroom left | Marge restante |
| `dash.worst_phase` | Busiest phase | Phase la plus chargée |
| `dash.published` | Published to charger | Publiés à la borne |
| `dash.pause` | Pause charging | Mettre en pause |
| `dash.pause_confirm` | Pause vehicle charging? It stops cleanly in about 2 minutes. | Mettre la charge en pause ? Elle s'arrête proprement en 2 minutes environ. |
| `dash.resume` | Resume charging | Reprendre la charge |
| `dash.resume_confirm` | Resume vehicle charging? | Reprendre la charge du véhicule ? |
| `dash.paused_banner` | Charging paused (load-shedding) | Charge en pause (délestage) |
| `dash.escalation_banner` | Sustained overload — clean stop in progress | Dépassement prolongé — arrêt propre en cours |
| `dash.backup_banner` | Running on Home Assistant backup (degraded) | Fonctionne sur le secours Home Assistant (dégradé) |
| `dash.failsafe_banner` | No measurement — charging blocked for safety | Aucune mesure — charge bloquée par sécurité |
| `dash.off_banner` | Regulation OFF — charger at full power, contract not protected | Régulation désactivée — borne à pleine puissance, abonnement non protégé |
| `dash.settings` | Settings | Réglages |
| `dash.contract_limit` | Contract limit (A per phase) | Limite d'abonnement (A par phase) |
| `dash.buffer` | Safety buffer (%) | Réserve de sécurité (%) |
| `dash.bias` | Slowdown (bias, A) | Ralentissement (biais, A) |
| `dash.bias_applied` | Slowdown applied | Ralentissement appliqué |
| `dash.diagnostics` | Diagnostics | Diagnostic |

State mapping (display copy for `sensor.loadpilot_state` /
`sensor.loadpilot_twc_source_active`): see `UX.md` §3.3 — same table, to
be used verbatim in `translations/…entity…state` blocks if the specialist
translates entity states.

---

## §Demandes (gaps found while designing against CONTRACTS.md §3/§4 — for the orchestrator; NOT invented in any YAML)

1. **Vehicle-side charging current missing.** The pilot user asks to see
   « le courant de la voiture ». §3.1 exposes the *published* setpoint and
   the house-side *measured* values, but not the current actually drawn at
   the wall connector. v0 fallback used in the cards: show
   `sensor.loadpilot_twc_published_current_l1` with the honest label
   “Published to charger”. Request: a `sensor.loadpilot_twc_charger_current`
   (A, TWC-side) if the firmware can source it (e.g. local TWC vitals
   pattern, docs/50_COUCHE_HA.md §6).
2. **No explicit `paused` state.** `sensor.loadpilot_state` has no value
   for “paused by bias”. The cards infer it from
   `sensor.loadpilot_twc_bias_applied >= 15`, which is fragile. Request:
   either a `paused` value on `sensor.loadpilot_state` or a
   `binary_sensor.loadpilot_paused`.
3. **Vehicle state of charge** — out of scope v0 (no vehicle API,
   ARCHITECTURE.md non-goals): the card ships a commented optional slot
   where users plug their own SoC entity. No contract change requested,
   noted for the record.
