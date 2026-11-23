# code_source : du scanner DICOM aux os en STL (Seg-Maillage)

| Fichier | Rôle |
|---|---|
| `etape1_lecture_dicom.py` | inventaire des séries, tri des coupes, valeurs en HU, matrice voxel vers mm (LPS) |
| `etape2_segmentation.py` | lissage, seuil de l'os, graines (seuil qui monte), croissance de région compétitive, recollage |
| `etape3_identification.py` | noms des os (forme et voisinage), tête fémorale (sphère), fibula, fabelles, points de l'utilisateur |
| `etape4_maillage.py` | remplissage, marching cubes, lissage, décimation, affinage à demi-hauteur, STL et `segmentation.seg.nrrd` |
| `etape5_controle.py` | sensibilité au seuil (± 50 HU), aperçus PNG, `rapport.md` et `rapport.json` |
| `parametres.py` | tous les réglages, au même endroit |
| `lancer_tout.py` | les étapes 1 à 5 en une commande |
| `vtk_leger.py` | VTK sans le rendu (démarrage plus rapide) |
| `tests/test_chaine.py` | test automatique sur un faux scanner de géométrie connue |

L'application (`../application/`) appelle exactement ces fonctions. La méthode est expliquée dans
`../segmentation_maillage/main.pdf`.

```bash
python lancer_tout.py --liste
python lancer_tout.py --serie hip_to_knee
python lancer_tout.py --dossier "D:/CT chien 12" --sortie "D:/resultats" --seuil 250 --ras
python tests/test_chaine.py
```
