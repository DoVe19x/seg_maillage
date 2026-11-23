# Seg-Maillage

Application de **segmentation osseuse** et de **maillage 3D** à partir d'un scanner (CT) : elle lit un dossier DICOM,
sépare chaque os, lui donne un nom (fémur, tibia, fibula...) et écrit un fichier STL étanche par os, dans les
coordonnées du scanner. L'interface montre le scanner en coupes et les os en 3D, comme 3D Slicer, et permet de
corriger le résultat.

Seg-Maillage reprend la **partie 1** de l'application CT-CORA3D (étapes 1 à 5 : du DICOM aux STL). Les étapes 6
(repères anatomiques) et 7 (guides de coupe) restent dans CT-CORA3D.

Projet de Dorian Verstappen (Master en ingénierie biomédicale, ECAM).

## Lancer

* **macOS** : double-clic sur `Seg-Maillage.app` (à refaire si besoin : `bash application/creer_app_mac.sh`).
* **Windows** : double-clic sur `Lancer sur Windows.bat`.
* **Terminal** : `cd application` puis `../../.venv/bin/python serveur.py` (options `--dossier`, `--resultats`,
  `--port`, `--sans-fenetre`).

Python 3.10 ou plus récent. Les lanceurs utilisent l'environnement `PMD2/.venv` s'il contient les bibliothèques
(`application/requirements.txt`), sinon ils en créent un au premier lancement. La fenêtre native (pywebview) est
installée une fois hors du dossier ; sans elle, l'interface s'ouvre dans Chrome ou Edge.

Dossier DICOM par défaut : `seg_maillage/dicom/` s'il existe, sinon `CT-CORA3D/dicom/` (projet voisin) ; le bouton
« Changer de dossier » en choisit un autre.

## Contenu

| Dossier ou fichier | Contenu |
|---|---|
| `application/` | serveur local (`serveur.py`), fenêtre native (`fenetre.py`), interface (`interface/`), lanceur macOS |
| `code_source/` | étapes 1 à 5, réglages (`parametres.py`), ligne de commande (`lancer_tout.py`), test du faux scanner |
| `exemples/` | les trois séries du lévrier déjà segmentées (copiées dans `resultats/` au démarrage) |
| `resultats/` | créé au premier lancement : un dossier par série (STL, `segmentation.seg.nrrd`, rapports, aperçus) |
| `segmentation_maillage/` | la **documentation** (document LaTeX et PDF, figures, schémas draw.io) et l'étude de convergence éléments finis du fémur |
| `segmentation_maillage_overleaf.zip` | la documentation prête à importer dans Overleaf |

## Ligne de commande

```bash
cd code_source
python lancer_tout.py --liste                  # séries du dossier DICOM
python lancer_tout.py --serie knee_to_ankle    # une série (étapes 1 à 5)
python tests/test_chaine.py                    # test sur un faux scanner (2 s)
```

## Licence

MIT (voir `LICENSE`). Three.js (interface) : licence MIT, `application/interface/vendor/LICENSE-three.txt`.
