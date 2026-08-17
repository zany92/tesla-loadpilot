# DESIGN — Switch « compteur absent » : faire TAIRE le serveur Modbus à chaud

> **IMPLÉMENTÉ le 17/08 soir (flash n° 2) — PAS ENCORE TESTÉ.** Le switch
> (`set_address(245)` / retour `set_address(1)`, livré OFF, jamais
> restauré au boot) compile et est en place sur le site (ESPHome 2026.7.4)
> et dans le firmware générique `esphome/packages/twc-core.yaml`
> (« Meter Absent (test) », id `twc_meter_server` sur le serveur Modbus).
> Le test du repli documenté « loss of meter → 6 A max » reste à jouer.
>
> ~~**Statut : ÉTUDE DE FAISABILITÉ — verdict : OUI, voie propre trouvée.**~~
> Objectif : pouvoir simuler à chaud la disparition du compteur émulé pour
> tester (puis éventuellement exploiter) le repli documenté de la borne :
> « loss of meter connection → 6 A maximum output » (app note DPM Tesla,
> rev 1.2, jan 2024 — BEHAVIOR.md §4). Sources examinées : code du
> composant `modbus_server` et du hub `modbus` d'ESPHome (branche dev,
> récupéré via l'API GitHub le 17/08 ; voir caveat de version §5).

## 1. La distinction qui gouverne tout : se taire ≠ répondre une erreur

Un compteur ABSENT, vu du maître Modbus (la borne, poll ~190 ms, deadline
de réponse ~66 ms), c'est un **silence** : aucune trame de réponse, le
poll expire. C'est ce que produit un câble coupé — et c'est le déclencheur
documenté du repli 6 A. Trois comportements très différents sont à notre
portée, et il ne faut pas les confondre :

| Comportement | Vu de la borne | Comment l'obtenir |
|---|---|---|
| **Silence** (compteur absent) | timeout de poll, retries | changement d'adresse esclave à chaud (§2) |
| **Exception Modbus** (compteur présent mais en panne) | réponse `SERVICE_DEVICE_FAILURE` | `read_lambda` qui « décline » (§3) |
| **Valeurs de repli** (compteur sain qui ment) | mesures normales | ce qu'on fait déjà (fail-safe `main_breaker`) |

## 2. La voie propre : `set_address()` à chaud — VÉRIFIÉE SUR SOURCE

### 2.1 Ce que dit le code

- `ModbusServerDevice` (base de `ModbusServer`) expose publiquement
  `void set_address(uint8_t address)` — l'adresse esclave est un simple
  membre consulté à CHAQUE trame, pas une constante de setup.
- Le dispatch du hub serveur (`ModbusServerHub::process_modbus_client_frame_`)
  fait `find_device_(address)` sur l'octet d'adresse de chaque requête ;
  si **aucun device enregistré ne porte cette adresse**, il marque la
  requête comme destinée à un pair du bus et **retourne sans rien
  émettre** (un log VERBOSE seulement, compilé hors binaire au niveau
  DEBUG → zéro écriture UART, zéro risque sur la deadline 66 ms).
- Conséquence : reprogrammer l'adresse du serveur à autre chose que 1 rend
  le nœud **strictement silencieux** pour les polls de la borne — le
  silence d'un vrai compteur débranché, réversible en une ligne.

### 2.2 Implémentation proposée (flash n° 2)

```yaml
modbus_server:
  - modbus_id: wallconn_modbus
    id: twc_meter_server          # ← AJOUT : le schéma le permet (declare_id)
    address: 1
    registers: [ ... inchangés ... ]

switch:
  - platform: template
    id: twc_meter_absent
    name: "TWC compteur absent (test)"
    icon: "mdi:meter-electric-outline"
    optimistic: true
    restore_mode: RESTORE_DEFAULT_OFF     # jamais fantôme après reboot
    on_turn_on:
      - lambda: 'id(twc_meter_server)->set_address(245);'
    on_turn_off:
      - lambda: 'id(twc_meter_server)->set_address(1);'
```

Détails vérifiés :

- **245** : adresse esclave valide (1-247), non nulle (0 = broadcast,
  interdit — le hub dispatcherait les écritures broadcast à tous les
  devices), et qu'aucun maître ne pollera jamais sur ce bus point-à-point.
- Thread-safety : lambdas de switch et traitement des trames tournent
  tous deux dans la boucle principale ESPHome (mono-thread) — pas de
  changement d'adresse possible au MILIEU d'une trame.
- Effet de bord bénin : le hub note la requête comme « pour un pair » et
  s'attend à une réponse de pair qui ne viendra jamais
  (`expecting_peer_response_`) ; ce marqueur est écrasé au poll suivant —
  simple bruit de comptabilité interne, aucun log au niveau DEBUG.
- `recompute_ct` continue de tourner normalement (les globals `ct*`
  restent calculées) : ON/OFF du switch est une bascule de VISIBILITÉ
  seule, la reprise republie des valeurs fraîches instantanément.

### 2.3 Ce que ça permet

1. **Le test du repli 6 A** enfin exécutable proprement : basculer en
   pleine charge, chronométrer la détection borne, mesurer le courant de
   repli réel (6 A documentés, 5 A « regulated floor » rapporté par PVi1
   sur 26.18 — divergence à trancher), observer `evse_state`, puis
   rétablir et observer la reprise.
2. **Un mode dégradé volontaire potentiellement précieux** : compteur
   absent = charge plafonnée ~6 A ≈ 4,1 kVA tri — une charge LENTE MAIS
   SÛRE, alors que notre fail-safe actuel (`main_breaker`) BLOQUE tout.
   Si le test confirme le repli, « couper le compteur » devient une
   alternative de repli quand la chaîne de mesure est malade longtemps
   (à arbitrer plus tard ; le fail-safe bloquant reste le défaut sûr).
3. **Une question de recherche** : l'absence de compteur remet-elle le
   score de confiance à zéro ? Si oui, une séquence
   absence → réapparition pourrait être un raccourci de purge de la
   défiance (vs les heures de signal honnête). À tester en dernier.

## 3. La voie « exception » : les `read_lambda` savent décliner — mais ce n'est pas le silence

Trouvaille de lecture du source, utile mais différente : une
`read_lambda` du composant peut retourner un **optional vide**
(`return {};`) — le commentaire d'en-tête du composant est explicite :
« an empty optional declines the read, answering the whole request with a
SERVICE_DEVICE_FAILURE exception ». Nos lambdas actuelles retournent des
valeurs nues (conversion implicite en optional plein).

- Donc `read_lambda: "if (id(meter_absent_flag)) return {}; return id(ct1_current_a);"`
  est possible SANS toucher à l'adresse — mais la borne reçoit alors une
  **réponse d'exception**, pas un silence : un compteur présent qui se
  déclare en panne. Réponse émise, CRC valide, deadline tenue.
- **Attention (piège demandé en mission)** : ne pas répondre est différent
  de répondre 0, ET différent de répondre une exception. Il n'existe
  AUCUN hook pour « ne pas répondre » depuis une read_lambda : le retour
  vide déclenche l'exception, pas le mutisme. Le seul mutisme accessible
  est l'échec de résolution d'adresse (§2).
- Intérêt réel : une **expérience n° 2** — la borne distingue-t-elle
  « meter absent » (timeout) de « meter faulty » (exception) ? Le repli
  6 A est documenté pour la perte de CONNEXION ; le comportement sur
  exception n'est documenté nulle part. Deux switchs de test valent mieux
  qu'un, et l'implémentation coûte trois lignes par registre (ou un seul
  registre-test 0xF4 pour commencer).

## 4. Options examinées et rejetées

| Option | Verdict | Raison |
|---|---|---|
| Désactiver l'UART à chaud | ❌ rejeté | aucune API ESPHome ; passer sous le composant avec `uart_driver_delete()` esp-idf est fragile (le hub garde ses buffers), non réversible proprement sans reboot |
| Boucle de reboot (« crude reboot loop ») | ❌ rejeté | ce nœud est AVANT TOUT la sécurité eau/forage (relais vannes, sonde forage) : chaque reboot coupe tout ; et un reboot vécu (~1 min de silence Modbus) n'a même pas suffi à purger la défiance |
| Relais physique sur le RS485 (plan B matériel) | ⚠️ en réserve | fonctionne à coup sûr (vrai silence électrique) mais matériel en plus sur un nœud de prod, intervention près du 230 V de la borne (disjoncteur coupé), et inutile si §2 est validé. Ne le câbler que si le test §2 révélait un comportement borne dépendant de la couche physique (improbable : le maître ne voit que des octets) |
| Répondre des zéros / `main_breaker` | ❌ hors sujet | c'est un compteur SAIN qui ment — déjà notre fail-safe ; ne teste pas le repli « absent » |
| `courtesy_response` du composant | ❌ hors sujet | complète les lectures d'adresses non mappées d'un même serveur ; sans effet sur le mutisme |

## 5. Caveats honnêtes

1. **Version** : lecture faite sur la branche dev d'ESPHome (post-2026.7,
   des dépréciations 2026.8 visibles dans `modbus.h`). L'API
   `set_address()` publique et le dispatch silencieux « pair » sont
   structurels (un esclave RS485 DOIT se taire pour les adresses des
   autres — c'est le protocole), donc très stables ; vérifier quand même
   à la compilation 2026.7.4 que `id(twc_meter_server)->set_address(...)`
   compile tel quel. Si le générateur refuse l'`id:` sur `modbus_server`
   en 2026.7.4 (schéma plus ancien), le repli est la voie §3 en attendant
   une montée de version.
2. **Comportement borne non garanti** : le repli 6 A est documenté par
   Tesla, mais la défiance (§4 BEHAVIOR.md) a prouvé l'existence de
   couches non documentées. Klangen82 #1 a vu un « fail-safe mode » sur
   un simple échelon permissif : une RÉAPPARITION du compteur en pleine
   session est exactement le genre de discontinuité qui pourrait latcher
   la défiance. Protocole de test en conséquence : créneaux courts,
   compteur de cycles contacteur avant/après, détecteur de défiance armé,
   voiture à faible courant, app Tesla à portée pour relancer (abandon
   véhicule après ~3 sessions perturbées).
3. **Pendant le silence, le levier compteur n'existe plus** : ni biais, ni
   STOP, ni escalade — la borne est seule (repli 6 A attendu). Les seuls
   leviers restants sont Fleet/app. Le switch doit rester un outil de
   TEST tant que le comportement n'est pas caractérisé ; côté HA,
   prévoir une notification si `twc_meter_absent` reste ON > 30 min
   (garde-fou contre l'oubli — précédent : biais oublié → filet G.7).
4. **Interférence de mesure** : compteur absent ≠ mesure absente — nos
   sources UDP/HA continuent d'alimenter le nœud et la couche HA voit
   toujours la vraie conso. Seule la borne devient aveugle. C'est le
   design voulu (tester SA réaction, pas dégrader la nôtre).

## 6. Recommandation

Inclure au flash n° 2 : l'`id:` sur `modbus_server` + le switch §2.2
(coût quasi nul, OFF par défaut, ne change RIEN tant qu'on n'y touche
pas). Le test du repli 6 A lui-même est une CAMPAGNE séparée, après la
validation de la loi covariante — ne jamais mélanger deux expériences sur
la confiance de la borne dans la même fenêtre.
