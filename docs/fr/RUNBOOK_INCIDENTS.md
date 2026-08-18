> 🇬🇧 [English version](../en/RUNBOOK_INCIDENTS.md)

# Runbook incidents : les trois modes de défaillance que vous rencontrerez vraiment

> Destiné à l'exploitant, volontairement court. Chaque signature et chaque
> remède ci-dessous ont été **vécus et mesurés** sur l'installation de
> référence (fw 26.18, 17/08/2026). Mécanismes et preuves :
> [`BEHAVIOR.md`](BEHAVIOR.md) (sections référencées incident par
> incident). Les constantes sont des données de calibration : voir
> BEHAVIOR §10 avant de s'y fier sur un autre firmware.

## 1. Défiance : la borne cesse de croire le compteur

**Ce que c'est.** Un état latché dans lequel la borne ignore entièrement
le compteur émulé : plus de modulation de service, plus de morsures de
protection, ordres d'arrêt au-dessus de L ignorés pendant des minutes.
BEHAVIOR §4.

**Signature / détecteur.**
- Valeur publiée **soutenue > L (≥ L + 0,45)** sans que le courant
  véhicule ne bouge : le détecteur de référence se déclenche sur
  publié > 21,45 pendant 120 s avec véhicule > 9 A.
- Ne concluez **PAS** à la défiance sur « pas de réaction à publié ≤ L » :
  à L exactement, la micro-loi dit HOLD (nominal). Seuls des ordres
  ignorés strictement au-dessus de L prouvent la défiance (BEHAVIOR §4,
  note de requalification).
- La porte de démarrage de charge continue de fonctionner pendant la
  défiance (démarrage refusé à publié > L − 5, accepté en dessous) : un
  refus ou une acceptation corrects ne prouvent rien sur la confiance,
  dans un sens comme dans l'autre.

**Causes fréquentes (à éviter).**
- Une valeur publiée sous le courant propre de la borne (glitch compteur).
- Une rampe véhicule non répercutée en 1:1 dans le signal publié (clamp
  saturé, ou un gain effectif en contrainte < ~0,5 : le plancher de
  dilution, BEHAVIOR §3).

**Remède / protocole de récupération (validé une fois, le 17/08 au soir).**
1. Cessez de lutter : relâchez le biais, laissez la couche HA délester
   les équipements domestiques pour la protection (ce chemin reste
   vivant).
2. Coupure secteur (power-cycle) de la borne (disjoncteur off/on). Une
   coupure secteur **seule** n'a pas suffi à récupérer dans notre test :
   ne sautez pas l'étape 3.
3. **~2 h de signal honnête** : publiez la mesure brute 1:1 (mode
   ombre/RAW), sans clamp, sans biais.
4. Premier redémarrage de session **maison calme**, pour que la rampe
   d'ouverture soit intégralement répercutée (un démarrage en saturation
   peut re-latcher la défiance à la seconde une).
5. Preuve de récupération = un ordre d'arrêt à L + 0,1 honoré en quelques
   secondes.

## 2. Yo-yo en boucle fermée : la loi obéit trop bien

**Ce que c'est.** Sous une contrainte soutenue, la boucle co-variante
peut pomper : véhicule cyclant à **±2,5 A, période ~20 s** ; après ~7
excursions, l'intégrale d'excès atteint le seuil de coupure et le
contacteur s'ouvre. Ce n'est pas de la défiance : chaque ordre est
honoré. BEHAVIOR §8 (addendum du soir) et §2.

**Réglages.**
- Couple validé : **gain 0,5 / emax 1,0**. Gardez-le.
- **N'amortissez jamais le yo-yo en baissant le gain** : sous ~0,5 de
  gain en contrainte, c'est de la dilution et la défiance se latche en
  une seule rampe : strictement pire que le yo-yo (BEHAVIOR §3, plancher
  de gain).

**Remède.**
- Immédiat : résolvez la contrainte soutenue avec la **pause** de la
  couche HA (biais), ne laissez pas la boucle pomper jusqu'à la coupure
  intégrale.
- Structurel : la variante B de la loi co-variante (réponse asymétrique /
  coups de frein un cycle sur deux), en cours de conception, voir
  [`DESIGN_LOI_COVARIANTE.md`](DESIGN_LOI_COVARIANTE.md).

## 3. Démarrage de charge refusé : le plus souvent, pas un incident

**Ce que c'est.** Le véhicule est branché, rien ne démarre (la borne peut
clignoter). Si la valeur publiée est **> L − 5**, c'est le contrôle
d'admission normal de la borne : puissance disponible insuffisante. C'est
la protection qui fonctionne, pas une panne. BEHAVIOR §4 (micro-loi).

**Remède.**
- **Attendez.** Le démarrage est accepté dès que la valeur publiée
  descend sous L − 5 (fin d'un appel domestique, ou relâche du
  biais/pause).
- Si le refus persiste avec une valeur publiée visiblement basse,
  vérifiez que le fail-safe n'est pas armé (aucune source de mesure saine
  → publié = main_breaker → marge 0 par conception ; vérifiez le nœud
  compteur et son capteur « TIC Alive »).
- Après **plusieurs** sessions interrompues, le véhicule abandonne en
  silence (`evse_state` 9, zéro alerte borne) : celui-là exige l'app ou
  un débranchage/rebranchage, voir BEHAVIOR §5.
