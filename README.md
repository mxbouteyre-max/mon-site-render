# Site d'extraction de données optiques

Ce dépôt centralise l'ensemble des fichiers permettant de faire tourner le site disponible à l'adresse suivante : **https://extractionsite.onrender.com/**

---

## Contexte

Ce travail a été réalisé dans le cadre d'un stage universitaire de fin de L3 MIASHS. La mission principale était d'automatiser la collecte de données relatives aux enseignes d'optique en France, et de développer une interface web permettant de piloter et d'exploiter ces données facilement, y compris sans intervention technique.

---

## Structure du dépôt

```
/
├── app.py                        # Serveur Flask (backend)
├── index.html                    # Interface d'extraction
├── excel-merger.html             # Outil de fusion Excel
├── fusion-colonnes.html          # Outil de fusion de colonnes
├── parser_linkedIn.html          # Alumni Scout (parser LinkedIn)
├── information.html              # Documentation du site
├── video_utilisation_site.mp4    # Tutoriel vidéo
├── requirements.txt              # Dépendances Python
└── code_extraction/              # Scripts Python de scraping (un par enseigne)
```

---

## Outils disponibles

### 1. Extraction de données — `index.html`

Interface principale du site. Elle liste les scripts Python du dossier `code_extraction/` et permet de lancer leur exécution à distance via le serveur Flask.

**Fonctionnalités :**
- Sélection individuelle des scripts à exécuter (10 maximum à la fois)
- Chrono estimé calculé automatiquement selon les scripts sélectionnés, avec décompte en temps réel pendant l'exécution
- Console de suivi en temps réel (sortie de chaque script)
- File d'exécution avec statut par script (en attente / en cours / succès / erreur)
- Bouton d'arrêt d'urgence
- Export des données au format `.xlsx` en feuille unique ou multi-feuilles (un onglet par enseigne)
- Suppression automatique des fichiers temporaires côté serveur après téléchargement

### 2. Fusion et mise à jour Excel — `excel-merger.html`

Outil de comparaison et de mise à jour de fichiers Excel, fonctionnant entièrement dans le navigateur (aucune donnée envoyée au serveur).

**Fonctionnalités :**
- Chargement de deux fichiers (`.xlsx`, `.xls`, `.csv`)
- Sélection d'une colonne clé pour faire correspondre les lignes entre les deux fichiers
- Indicateur du nombre de correspondances trouvées
- Deux modes d'opération :
  - **Fusion** : enrichit le fichier maître avec les données du fichier de mise à jour
  - **Surlignage** : génère un fichier Excel avec les lignes communes surlignées dans la couleur choisie
- Sélection des colonnes à conserver dans le fichier final
- Prévisualisation des premières lignes avant export
- Export `.xlsx` téléchargeable directement

### 3. Fusion de colonnes — `fusion-colonnes.html`

Outil complémentaire permettant de fusionner des colonnes au sein d'un fichier Excel.

### 4. Alumni Scout — `parser_linkedIn.html`

Outil de parsing de profils LinkedIn sauvegardés en HTML, conçu pour identifier des diplômés de l'Institut Supérieur d'Optique (ISO) dans un réseau.

**Fonctionnalités :**
- Bookmarklet intégré pour capturer instantanément un profil LinkedIn en un clic (sans télécharger les ressources inutiles)
- Analyse de plusieurs profils en une seule opération
- Extraction automatique : nom, prénom, localisation, poste actuel, entreprise, formation, email, URL du profil
- Détection automatique d'un diplôme ISO (recherche sur toute la section Formation)
- Export CSV compatible Excel

### 5. Documentation — `information.html`

Page de documentation décrivant le fonctionnement de chacun des outils du site.

### 6. Tutoriel vidéo — `video_utilisation_site.mp4`

Vidéo de présentation du site expliquant le fonctionnement des trois outils principaux, accessible depuis le lien **▶ Tutoriel** dans le header de la page d'extraction.

---

## Scripts de scraping (`code_extraction/`)

Le dossier contient un script Python par enseigne d'optique. Chaque script collecte pour chaque point de vente : nom, adresse, code postal, ville, département, téléphone, email, coordonnées GPS et URL de la fiche.

Les enseignes couvertes incluent notamment : Krys, Optic 2000, Grand Optical, Générale Optique, Optical Center, Afflelou, Atol, Lissac, Lynx Optique, Jimmy Fairly, GrandOptical, Écouter Voir, Maneo, Visuals, et une trentaine d'autres réseaux.

Tous les scripts fonctionnent sans Selenium (compatibles Render free tier) et gèrent automatiquement la déduplication des magasins.

---

## Backend — `app.py`

Serveur Flask déployé sur Render. Il assure :
- Le service des pages HTML
- L'exécution des scripts Python à la demande via l'API `/api/run`
- Le suivi de l'état des jobs en temps réel (`/api/status`)
- La fusion des fichiers CSV/XLSX produits en un seul fichier final (`/api/download_all`)
- La normalisation automatique des noms de colonnes entre les différentes sources (via un référentiel de colonnes et un système d'alias)
- La suppression des fichiers temporaires après téléchargement (`/api/clear_outputs`)

---

## Déploiement

Le site est hébergé sur **Render (free tier)**. Le dépôt GitHub est connecté à Render — tout push sur la branche principale déclenche un redéploiement automatique.

Les dépendances Python sont listées dans `requirements.txt`.
