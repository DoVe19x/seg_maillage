# application : interface et serveur local de Seg-Maillage

```
fenêtre native (fenetre.py : pywebview ; à défaut Chrome / Edge)
  interface/index.html + app.js : coupes du scanner, os en 3D (Three.js), liste des os, corrections
        │  requêtes HTTP locales (127.0.0.1 uniquement : rien ne sort de l'ordinateur)
        ▼
serveur.py (Python) ──► code_source/etape1 … etape5 ──► seg_maillage/resultats/<série>/
```

* `serveur.py` démarre un serveur web local sur un port libre, copie les exemples dans `resultats/`, liste les séries
  du dossier DICOM et ouvre la fenêtre. Les calculs tournent un à un dans le fil principal (VTK l'exige sur macOS) ;
  pendant un calcul, l'ordinateur ne se met pas en veille. Seule la page de l'application peut parler au serveur
  (en-têtes Host et Origin vérifiés).
* Actions : inventaire, ouverture d'une série, segmentation (étapes 1 à 5), renommer un os, séparer un segment par des
  points (enregistrés dans `graines.json`), oublier les points.
* `lancer_mac.sh` (appelé par `Seg-Maillage.app`) et `../Lancer sur Windows.bat` choisissent l'environnement Python et
  installent au besoin les bibliothèques et la fenêtre. Journal : `~/Library/Logs/SegMaillage.log` (macOS),
  `%LOCALAPPDATA%\SegMaillage\SegMaillage.log` (Windows).
* `creer_app_mac.sh` refait `../Seg-Maillage.app` à partir de `lanceur_mac.applescript` et de l'icône.
