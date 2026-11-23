# Étude de convergence du maillage éléments finis du fémur (lévrier, appui statique)

Étude « comme dans Abaqus » : le même calcul est refait avec des maillages de plus en plus fins et quatre types
d'éléments (C3D4, C3D10, C3D8, C3D20). On trace la contrainte (MPa) en fonction du nombre de nœuds et du nombre
d'éléments, jusqu'au plateau. Le calcul est fait par un petit code d'éléments finis en Python (`ef.py`) qui reprend les
éléments d'Abaqus (même ordre des nœuds, même intégration). Chaque maillage est aussi écrit en fichier `.inp`, pour
refaire l'étude dans Abaqus.

## Le cas de charge

| | |
|---|---|
| Os | fémur complet, `donnees/femur.stl` (série hanche et genou du lévrier), dans le repère anatomique de l'étape 6 de CT-CORA3D (`donnees/reperes_femur.json`) : X latéral, Y proximal, Z caudal (membre gauche ramené à un droit) |
| Situation | chien debout, immobile : calcul statique linéaire |
| Force | 1/4 du poids du corps : 30 kg × 9,81 / 4 = 73,6 N (masse : standard de race du lévrier, 27 à 32 kg) |
| Point et direction | centre de la tête fémorale, dans la direction de l'axe mécanique (centre de la tête vers le milieu des points distaux des condyles) |
| Transmission | cupule rigide liée à la tête par une contrainte Tie (calotte de ± 60° autour de l'axe), point de référence RP au centre de la tête |
| Appui | encastrement des condyles (nœuds à moins de 10 mm de l'extrémité distale) |
| Matériau | élastique linéaire, homogène, isotrope : E = 17 000 MPa, ν = 0,3 ; os plein |
| Résultat suivi | contrainte de von Mises maximale aux nœuds entre 40 et 60 % de l'axe mécanique |

Le schéma `../images/schema_femur_chargement.pdf` (source modifiable : `../schemas/femur_chargement.drawio`) montre le
fémur, l'axe mécanique, la force, la cupule liée par la contrainte Tie et l'encastrement.

## La géométrie figée

Une étude de convergence n'a de sens que si la géométrie ne change pas. La « pièce » est construite une fois :
maillage TetGen de base (éléments de 7 mm, 533 sommets), passé en tétraèdres quadratiques dont les nœuds milieux de
surface sont posés sur le STL (surface courbe, 98,3 cm³). Les maillages de l'étude en sont tirés :

| Élément | Abaqus | Maillage au niveau k |
|---|---|---|
| tétraèdre linéaire | C3D4 | chaque tétraèdre de base coupé en k³ tétraèdres |
| tétraèdre quadratique | C3D10 | le même, avec les nœuds milieux |
| hexaèdre linéaire | C3D8 | chaque tétraèdre de base coupé en 4 hexaèdres, puis chaque hexaèdre en k³ |
| hexaèdre quadratique | C3D20 | le même, avec les nœuds milieux |

Tous les nœuds sont placés par la transformation quadratique des tétraèdres de base : les éléments quadratiques
représentent exactement la pièce, les éléments linéaires s'en approchent quand k augmente. Pourquoi pas des facettes
planes : chaque arête entre deux facettes, là où la surface est concave, est un petit coin rentrant où la contrainte
ne converge pas (vérifié : le maximum se plaçait exactement sur ces arêtes).

## Fichiers

| Fichier | Rôle |
|---|---|
| `ef.py` | éléments C3D4, C3D10, C3D8, C3D20 ; assemblage ; résolution (directe, ou gradient conjugué + multigrille) avec la cupule rigide (Tie) ; contraintes aux nœuds ; écriture `.inp` |
| `maillages.py` | fémur dans le repère anatomique, axe mécanique, maillage de base, géométrie courbe, raffinement en k³ ; poutre de validation |
| `validation_poutre.py` | vérification du code : fonctions de forme, poutre console (charge répartie, puis force au bout par une cupule rigide) |
| `etude_femur.py` | l'étude ; écrit `resultats/convergence_femur.csv` et les figures `../images/femur_*` |
| `schema_femur.py` | le schéma draw.io du cas de charge |
| `donnees/` | `femur.stl` et `reperes_femur.json` (repères anatomiques calculés par l'étape 6 de CT-CORA3D : centre de la tête, points des condyles, repère de l'os) |
| `resultats/` | `convergence_femur.csv`, `validation_poutre.csv`, `validation_tie.csv`, figures en PNG |
| `abaqus/` | un fichier `.inp` par maillage, `femur_<élément>_k<k>.inp` (non suivi par Git, refait par `--inp`) |

## Lancer

```bash
python -m venv .venv_ef
.venv_ef/bin/pip install -r requirements.txt
.venv_ef/bin/python validation_poutre.py         # ≈ 1 min
.venv_ef/bin/python etude_femur.py --inp         # ≈ 20 min ; reprend là où il s'était arrêté
.venv_ef/bin/python etude_femur.py --figures     # figures seules, depuis le CSV
.venv_ef/bin/python schema_femur.py              # schéma (draw.io fermé pendant l'export)
```

## Refaire l'étude dans Abaqus

Chaque fichier `abaqus/femur_<élément>_k<k>.inp` est complet : nœuds, éléments, matériau `OS_CORTICAL`, point de
référence `RP` (centre de la tête), ensembles `TETE` (nœuds liés à la cupule), `ENCASTREMENT` (nœuds) et `MILIEU`
(éléments), la cupule rigide (`*Rigid Body, ref node=RP, tie nset=TETE` : les nœuds de la tête suivent le corps rigide
de RP), la force en RP (`*Cload`) et un pas statique. Dans Abaqus/CAE, cela revient à une pièce rigide « cupule » liée
à la surface de la tête par une contrainte Tie (Interaction, Constraint, Tie), ou à une contrainte Rigid body sur la
région de la tête. Lancer : `abaqus job=femur_C3D10_k2 interactive` ; dans le module Visualization, afficher S, Mises
et lire le maximum sur l'ensemble `MILIEU`.

Pour l'élément hexaédrique par défaut d'Abaqus, remplacer `type=C3D8` par `type=C3D8R` dans la ligne `*Element`
(intégration réduite avec contrôle du hourglass, non programmée dans `ef.py`). Petite différence attendue : Abaqus
extrapole les contraintes depuis les points de Gauss, `ef.py` les évalue directement aux nœuds. Les `.inp` n'ont pas pu
être testés dans Abaqus (pas de licence sur la machine où ils ont été écrits) : leur format suit le manuel d'Abaqus, et
les mêmes maillages, avec les mêmes conditions, sont résolus par `ef.py`.
