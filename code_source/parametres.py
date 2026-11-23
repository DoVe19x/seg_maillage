"""
parametres.py : TOUS les réglages du programme, au même endroit.

Rôle    : centraliser les valeurs qu'un utilisateur peut avoir à changer (dossiers, seuils, tailles, lissage).
Entrées : aucune (fichier de configuration lu par les autres scripts).
Sorties : aucune.

Règle : aucune autre valeur « magique » ne doit apparaître dans les scripts. Chaque valeur indique son origine :
document Best_Position (BP), littérature, ou mesure faite sur les CT du dossier (lévrier, 3 séries, 2013).
Les HU sont des unités Hounsfield : air -1000, eau 0, tissus mous 0 à 80, os spongieux 250 à 700, corticale 1200 à 1500.
"""
from pathlib import Path


# --------------------------------------------------------------------------- version
# Version du programme, écrite dans chaque fichier produit (rapport.json, en-tête des STL). À augmenter à chaque
# livraison.
VERSION = "1.0"
PROGRAMME = f"Seg-Maillage {VERSION}"

# --------------------------------------------------------------------------- dossiers
RACINE = Path(__file__).resolve().parent.parent           # dossier seg_maillage/
# Dossier DICOM fouillé par défaut : seg_maillage/dicom/ s'il existe ; sinon celui du projet voisin CT-CORA3D (les
# séries du lévrier, ≈ 17 Go, ne sont pas recopiées) ; sinon le dossier seg_maillage lui-même. Un autre dossier se
# choisit dans l'application. Les DICOM ne vont jamais sur GitHub (.gitignore).
DOSSIER_DICOM = next((d for d in (RACINE / "dicom", RACINE.parent / "CT-CORA3D" / "dicom") if d.is_dir()), RACINE)
RESULTATS = RACINE / "resultats"                          # un sous-dossier par série : resultats/<série>/ (jamais sur GitHub)
# Exemples livrés (séries du lévrier déjà segmentées). Ils ne sont jamais modifiés : au démarrage, l'application copie
# dans resultats/ ceux qui n'y sont pas encore, et travaille sur la copie.
EXEMPLES = RACINE / "exemples"
IGNORES = {"resultats", "exemples", "code_source", "application", "segmentation_maillage", "__pycache__"}

# --------------------------------------------------------------------------- étape 1 : lecture DICOM
EPAISSEUR_MAX_MM = 1.0           # BP §3.1 : coupes ≤ 1 mm (au-delà : avertissement, le calcul continue)
TOLERANCE_ESPACEMENT = 0.05      # écart relatif toléré entre deux intervalles de coupes (sinon : coupes manquantes ?)
TOLERANCE_ORIENTATION = 1e-3     # cosinus directeurs identiques à 1e-3 près pour toutes les coupes d'une série

# --------------------------------------------------------------------------- étape 2 : segmentation
SIGMA_LISSAGE_MM = 0.35          # flou gaussien avant seuillage. Bruit mesuré dans les tissus mous : ≈ 49 HU (noyau
                                 # « BONEPLUS ») ; 0,35 mm le divise par ~2 sans effacer les interlignes (≥ 1 mm).
SEUIL_OS_HU = 226                # masque osseux. BP : « ≈ 200-300 HU pour l'os cortical, à ajuster » ; 226 HU est
                                 # le seuil « Bone (CT) » par défaut de Mimics, très utilisé en planification 3D.
MARGE_RECADRAGE_MM = 6.0         # marge autour des os denses quand on recadre le volume (économie de mémoire)

# Graines automatiques : « noyaux denses » obtenus en montant le seuil palier par palier. Un bloc qui se coupe en
# plusieurs morceaux qui persistent devient plusieurs graines (une par os). Réglages issus des essais sur le lévrier.
SEUIL_GRAINE_DEPART_HU = 500     # premier palier (au-dessus de l'os spongieux le moins dense)
SEUIL_GRAINE_MAX_HU = 1500       # dernier palier (corticale)
PAS_SEUIL_HU = 100
VOLUME_MIN_MORCEAU_MM3 = 300.0   # un morceau doit faire ≥ 0,3 cm³ pour devenir une graine (patella du lévrier ≈ 2 cm³)
PERSISTANCE_HU = 200             # … et garder ≥ VOLUME_PERSISTANCE_MM3 encore 200 HU plus haut (un vrai os a une
VOLUME_PERSISTANCE_MM3 = 50.0    # corticale dense ; un fragment d'os spongieux disparaît avant)
VOLUME_MIN_GRAINE_MM3 = 30.0     # bloc dense plus petit : pas de graine (bruit, calcification)
VOLUME_MIN_SEGMENT_MM3 = 50.0    # segment final plus petit : rattaché à son voisin, ou supprimé s'il est isolé

# Fusion des « sur-découpages » : quand un même os a été coupé en deux (souvent une épiphyse détachée de la
# diaphyse à haut seuil), les deux morceaux se touchent sur toute la section de l'os. Critère sans dimension :
# c* = surface de contact / V_min^(2/3). Mesuré : coupures d'un même os c* ≈ 5 ; vraies articulations c* ≤ 2,1.
RAPPORT_CONTACT_FUSION = 3.0

# --------------------------------------------------------------------------- étape 3 : identification et corrections
# Formes
LONGUEUR_OS_LONG_MM = 50.0       # os long : longueur ≥ 50 mm et allongement (L1/L2) ≥ 3
ALLONGEMENT_OS_LONG = 3.0
ALLONGEMENT_COMPACT = 3.5        # os « compact » (tarse, patella) : allongement < 3,5
VOLUME_MIN_NOMME_MM3 = 200.0     # en dessous de 0,2 cm³, un segment n'est jamais nommé automatiquement
# Objets non osseux (fantôme de calibration, tige) : densité homogène, pas d'os spongieux ni de moelle.
# Mesurés à l'INTÉRIEUR du segment (bords flous exclus), puis confirmés par l'absence de cavité : un os a une
# cavité médullaire ou de l'os spongieux à remplir, un fantôme est plein.
CV_MAX_OBJET = 0.2               # coefficient de variation des HU
FRACTION_SPONGIEUX_MAX_OBJET = 0.08   # fraction des voxels < 600 HU
CAVITE_MAX_OBJET = 0.05          # remplissage < 5 % du volume (fémur du lévrier : + 29 %)

# Hanche : la tête fémorale est quasi sphérique. L'interligne (ligne sombre entre tête et acétabulum) est révélé
# par un « chapeau haut-de-forme noir » (fermeture morphologique - image), puis une sphère est ajustée (RANSAC).
RAYON_VALLEE_MM = 1.0            # taille des vallées recherchées (interligne ≈ 1-2 mm)
PROFONDEUR_VALLEE_HU = 250       # profondeur minimale d'une vallée
HU_MIN_VALLEE = 150              # … et densité > 150 HU (écarte les cloisons graisseuses entre les muscles)
RAYON_RECHERCHE_TETE_MM = 35.0   # recherche autour du contact fémur / bassin
RAYON_TETE_MM = (4.0, 20.0)      # rayon plausible d'une tête fémorale de chien (toy → géant)
TOLERANCE_SPHERE_MM = 0.6        # un point de vallée appartient à la sphère s'il en est à moins de 0,6 mm
COUVERTURE_MIN_SPHERE = 0.4      # fraction des directions couvertes par des points de la sphère (lévrier : 70 %)
INLIERS_MIN_SPHERE = 150         # nombre minimal de points sur la sphère (lévrier : 1912)
MARGE_SPHERE_MM = 1.0            # graine « fémur » : sphère - 1 mm ; graine « bassin » : au-delà de sphère + 1 mm
# Garde-fous de la tête fémorale (09/11/2026, chien A de Zurich : la mandibule, articulée au crâne, avait été prise pour
# un fémur et le crâne pour le bassin) : un os qui porte des dents n'est pas un fémur. Émail des dents : des centaines
# à des milliers de voxels > 2250 HU (même avec le filtre « tissus mous », qui lisse les densités) ; os des membres :
# aucun (lévrier ≤ 1770 HU ; humérus, radius et ulna du chien A ≤ 2140 HU avec le filtre osseux, le plus net).
# La tête fémorale est petite devant le fémur (rayon / longueur : 5 % chez le lévrier), vérifié seulement si l'os
# n'est pas coupé par le champ du scanner.
HU_EMAIL_DENTS = 2250
VOXELS_MIN_DENTS = 30
RAPPORT_TETE_FEMUR_MAX = 0.09

# Fabelles (sésamoïdes du gastrocnémien, derrière les condyles fémoraux) : trop petites pour avoir une graine,
# elles sont collées au fémur ; on les en détache par un raffinement du fémur. Mesuré (lévrier) : 0,52 cm³, c* ≈ 0,5.
FRACTION_MAX_SESAMOIDE = 0.05    # < 5 % du volume du fémur
CSTAR_MAX_SESAMOIDE = 1.5        # contact faible (une coupure à travers l'os donne c* ≈ 5)

# Fibula : au milieu de la jambe, la fibula apparaît comme une petite tache séparée du tibia sur les coupes
# perpendiculaires à l'os. Aires mesurées (lévrier) : tibia ≈ 300 mm², fibula ≈ 17 mm².
PAS_TRANCHES_MM = 2.0
AIRE_MIN_FIBULA_MM2 = 3.0
RAPPORT_AIRE_FIBULA_MAX = 0.2    # aire fibula / aire tibia
SERIE_MIN_FIBULA = 0.15          # la fibula doit être vue séparée sur ≥ 15 % de la longueur (mesuré : 45 %)
SAUT_MAX_FIBULA_MM = 3.0         # d'une tranche à la suivante (2 mm), la petite tache se déplace de moins de 3 mm

# Graines de l'utilisateur (points nommés, enregistrés dans resultats/<série>/graines.json)
RAYON_GRAINE_MM = 2.5

# Noms des os (ceux du membre synthétique de la v2 + « tarse » du schéma du projet) et couleurs d'affichage.
NOMS_OS = {
    "femur": "fémur", "tibia": "tibia", "fibula": "fibula", "patella": "patella", "fabelles": "fabelles",
    "talus": "talus", "calcaneus": "calcanéus", "tarse": "tarse (autres os)", "metatarses": "métatarses",
    "phalanges": "phalanges", "bassin": "bassin",
    # membre thoracique (patte avant), depuis le 09/11/2026 (cas de Zurich)
    "scapula": "scapula", "humerus": "humérus", "radius": "radius", "ulna": "ulna", "carpe": "carpe",
    "metacarpes": "métacarpes",
    "objet": "objet non osseux", "autre": "autre os",
}
COULEURS = {
    "femur": (0.89, 0.85, 0.74), "tibia": (0.80, 0.86, 0.95), "fibula": (0.95, 0.70, 0.45), "patella": (0.98, 0.55, 0.60),
    "fabelles": (0.85, 0.55, 0.85), "talus": (0.55, 0.85, 0.55), "calcaneus": (0.40, 0.70, 0.45), "tarse": (0.65, 0.90, 0.75),
    "metatarses": (0.95, 0.85, 0.40), "phalanges": (0.90, 0.75, 0.30), "bassin": (0.70, 0.70, 0.78),
    "scapula": (0.82, 0.78, 0.66), "humerus": (0.89, 0.85, 0.74), "radius": (0.80, 0.86, 0.95), "ulna": (0.95, 0.70, 0.45),
    "carpe": (0.65, 0.90, 0.75), "metacarpes": (0.95, 0.85, 0.40),
    "objet": (0.50, 0.50, 0.50), "autre": (0.62, 0.60, 0.56),
}
# Fichiers STL exportés : un par os nommé, plus des groupes. « tarse » = tous les os du tarse (schéma du projet).
GROUPES_EXPORT = {"tarse": ("talus", "calcaneus", "tarse")}
EXPORTER_AUTRES = False          # True : exporte aussi les os non nommés (autre_1.stl, …)

# --------------------------------------------------------------------------- étape 4 : maillage
RAYON_FERMETURE_MM = 1.0         # fermeture morphologique avant remplissage (bouche les pores de la corticale)
SIGMA_MAILLAGE_MM = 0.3          # flou du masque binaire avant « marching cubes » (supprime l'effet d'escalier)
ITERATIONS_LISSAGE = 20          # lissage « windowed sinc » de VTK : ne rétrécit pas le maillage (comme 3D Slicer)
BANDE_PASSANTE_LISSAGE = 0.05
TRIANGLES_MAX = 150_000          # décimation au-delà (≈ 7 Mo de STL par os)
REDUCTION_MAX = 0.75             # jamais plus de 75 % des triangles retirés
# Affinage « demi-hauteur » : un seuil bas (226 HU, corticale ≈ 1300 HU) place la surface ~1 écart-type du flou
# du scanner TROP À L'EXTÉRIEUR (fantôme de tests/test_chaine.py : +0,60 mm mesuré, +0,64 mm prévu). Chaque sommet
# est ramené au point où l'intensité vaut la moitié entre la corticale et le fond (bord vrai d'un bord flou).
AFFINAGE_DEMI_HAUTEUR = True
PROFIL_INTERIEUR_MM = 2.5        # profil d'intensité le long de la normale : de -2,5 mm (dans l'os)…
PROFIL_EXTERIEUR_MM = 2.0        # … à +2 mm (dehors)
CONTRASTE_MIN_HU = 300           # pic - fond minimal pour faire confiance au profil
DEPLACEMENT_MAX_MM = 1.5         # au-delà : profil douteux (articulation serrée…), sommet laissé en place
LISSAGE_DEPLACEMENT = 5          # passes de moyenne des déplacements entre sommets voisins
SYSTEME_COORDONNEES = "LPS"      # STL en coordonnées du scanner (BP §3.2) : LPS = DICOM, comme l'export par
                                 # défaut de 3D Slicer (≥ 4.11). "RAS" : x et y inversés.

# --------------------------------------------------------------------------- étape 5 : contrôle
VARIATION_SEUIL_HU = 50          # BP, hypothèse H2 : « variation du seuil ± 50 HU et mesure de l'impact »
ECART_SURFACE_CIBLE_MM = 0.5     # BP, H2 : le maillage coïncide avec la surface osseuse à moins de 0,5 mm
IMAGES_CONTROLE = True           # aperçus PNG (rendu 3D + coupes) dans resultats/<série>/
