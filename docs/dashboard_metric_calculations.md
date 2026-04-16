# Calculs techniques du dashboard

Ce document décrit les calculs utilisés pour dériver les métriques du dashboard à partir des données brutes Garmin normalisées.

## Sources brutes

- `activities`
  - source : activités Garmin normalisées depuis les exports importés
  - champs utilisés : `activity_type`, `activity_date`, `started_at`, `duration_seconds`, `distance_meters`, `average_hr`, `max_hr`, `training_load`, `raw_payload`
- `wellness_daily`
  - source : signaux wellness Garmin normalisés
  - champs utilisés : `metric_date`, `resting_hr`, `hrv_ms`, `sleep_duration_seconds`
- `heart_rate_zones`
  - source : seuils de zones cardio issus du profil Garmin
  - champs utilisés : `max_hr`, `zone1_floor`, `zone2_floor`, `zone3_floor`, `zone4_floor`, `zone5_floor`

## Règles de normalisation

- encodage texte : `UTF-8 + NFC` conformément à `ADR 005`
- running pris en compte :
  - `running`
  - `trail_running`
  - `treadmill_running`
  - `indoor_running`
- vélo pris en compte :
  - `cycling`
  - `bike`
  - `biking`
  - `road_biking`
  - `mountain_biking`
  - `indoor_cycling`
  - `virtual_ride`
  - `ebike`
  - `gravel_cycling`

## Volume running et vélo

### Volume running

- calcul journalier :
  - somme de `distance_meters` pour les activités running du jour
- unité affichée :
  - kilomètres
- conversion :
  - `distance_km = distance_meters / 1000`

### Volume vélo

- calcul journalier :
  - somme de `distance_meters` pour les activités vélo du jour
- unité affichée :
  - kilomètres

## Charge quotidienne

- calcul journalier :
  - somme de `training_load` pour les activités running du jour
- intention :
  - représenter la charge brute du jour sans moyenne glissante par défaut

## Charge relative

### Définitions

- `load_7d`
  - somme des charges quotidiennes des 7 derniers jours
- `load_28d`
  - somme des charges quotidiennes des 28 derniers jours
- charge chronique équivalente 7 jours :
  - `equivalent_chronic_load_7d = load_28d / 4`

### Formule

- `load_ratio_7_28 = load_7d / (load_28d / 4)`

### Interprétation

- `1.00`
  - la charge récente est cohérente avec la charge chronique ramenée à 7 jours
- `< 0.80`
  - retrait net par rapport au niveau chronique récent
- `0.80 - 1.20`
  - zone de lecture stable
- `> 1.20`
  - augmentation récente notable
- `> 1.30`
  - augmentation forte à surveiller

## Sommeil

### Série brute

- source :
  - `sleep_duration_seconds` dans `wellness_daily`
- conversion :
  - `sleep_hours = sleep_duration_seconds / 3600`
- agrégation :
  - moyenne journalière si plusieurs enregistrements wellness existent sur la même date

### Série lissée 7 jours

- formule :
  - moyenne glissante 7 jours sur `sleep_hours`
- usage :
  - optionnel uniquement
- mode par défaut :
  - brut

## FC repos

- série brute :
  - moyenne journalière de `resting_hr`
- pas de lissage par défaut

## HRV

### Série brute

- source :
  - `hrv_ms` dans `wellness_daily`
- agrégation :
  - moyenne journalière

### Série lissée 7 jours

- formule :
  - moyenne glissante 7 jours sur `hrv_ms`
- mode par défaut :
  - brut

## Cadence running

### Unité cible

- unité standard :
  - `spm` = `steps per minute`

### Extraction

Ordre de recherche dans le payload brut :

- `avgDoubleCadence`
- `averageDoubleCadence`
- `WEIGHTED_MEAN_DOUBLE_CADENCE`
- `WEIGHTED_MEAN_DOUBLECADENCE`
- `doubleCadence`
- sinon cadence running simple :
  - `avgRunCadence`
  - `averageRunCadence`
  - `WEIGHTED_MEAN_RUNCADENCE`
  - `WEIGHTED_MEAN_RUN_CADENCE`
  - `runCadence`
  - `cadence`

### Conversion

- si la valeur trouvée ressemble à une cadence "par jambe" (`<= 120`), conversion :
  - `cadence_spm = cadence * 2`
- sinon :
  - `cadence_spm = cadence`

## Allure running

- calcul journalier :
  - moyenne pondérée par durée des allures de course du jour
- formule activité :
  - `pace_min_per_km = (duration_seconds / 60) / (distance_meters / 1000)`

## FC running

- calcul journalier :
  - moyenne pondérée par durée des `average_hr` des activités running du jour

## Courbe allure / FC

### Entrées

- points issus des sorties running
- types de points :
  - résumé d’activité si la sortie est suffisamment longue et exploitable
  - splits / laps si disponibles et plausibles

### Filtres

- allure valide :
  - entre `2.5` et `12.0 min/km`
- FC valide :
  - entre `60` et `220 bpm`
- fragments trop courts exclus :
  - `< 120 s` et `< 500 m`

### Construction

- binning sur l’allure
- médiane pondérée de la FC par bin
- lissage isotone non décroissant de la FC

### Intention

- obtenir une relation monotone entre allure et FC
- éviter qu’un sprint court ou un split instable déforme la courbe

## Temps passé en zones FC

### Méthode

- approximation par activité
- chaque activité contribue avec :
  - sa `duration_seconds`
  - sa `average_hr`
- affectation de zone via :
  - seuils `heart_rate_zones` si disponibles
  - sinon fallback sur ratio de `max_hr`

### Limite connue

- ce n’est pas une intégration seconde par seconde
- c’est une répartition approximative pondérée par durée d’activité et FC moyenne

## Typage des séances running

### Types

- `Jogg facile`
- `Qualité`
- `Sortie longue`

### Priorité de classification

1. `Sortie longue`
2. `Qualité`
3. `Jogg facile`

### Heuristique sortie longue

- si `distance_meters` dépasse :
  - `max(percentile_85_distance_running, 12000)`
- ou si `duration_seconds` dépasse :
  - `max(percentile_85_duration_running, 4200)`

### Heuristique qualité

La séance est `Qualité` si elle n’est pas déjà `Sortie longue` et si au moins un signal fort est présent :

- présence explicite de structure workout ou de nombreux splits/laps
- `average_hr >= zone3_floor` si les seuils cardio sont disponibles
- ou `training_load / durée_en_heures >= 45`

### Sinon

- `Jogg facile`

## Références visuelles

- charge relative :
  - bande par défaut `0.80 - 1.20`
  - cible `1.00`
- cadence :
  - cible `170 spm`
  - bande par défaut autour de la distribution observée
- sommeil, HRV, FC repos :
  - bandes de lecture construites sur les percentiles de la série historique disponible

## Emplacement du code

- calculs analytiques principaux :
  - `coach_garmin/analytics_support.py`
  - `coach_garmin/analytics_series.py`
- projection runtime PWA :
  - `coach_garmin/pwa_service_runtime_support.py`
  - `coach_garmin/pwa_service_support.py`
- rendu UI :
  - `web/app.js`
