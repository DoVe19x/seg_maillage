"""
maillages.py : maillages volumiques du fémur (géométrie figée) et de la poutre de validation.

Rôle    : (1) lire le fémur (donnees/femur.stl) et le placer dans le repère anatomique (X latéral, Y proximal,
              Z caudal ; membre gauche ramené à un droit par symétrie), avec ses repères (centre de la tête...) ;
          (2) géométrie figée : un maillage de base en tétraèdres (surface remaillée de façon uniforme par pyacvd, puis
              TetGen), passé en tétraèdres quadratiques dont les nœuds milieux de surface sont posés sur le STL : la
              surface est courbe, c'est « la pièce » (comme une géométrie de CAO dans Abaqus) ;
          (3) raffinement : chaque tétraèdre de base est coupé en k³ tétraèdres, ou en 4 hexaèdres puis k³ ; tous les
              nœuds sont placés par la transformation quadratique de l'élément de base : la pièce ne change pas ;
          (4) poutre droite maillée en hexaèdres ou en tétraèdres, pour la validation du code.
Sorties : (X, conn) : coordonnées des nœuds (mm) et connectivité (indices à partir de 0, ordre d'Abaqus).
"""
import json

import numpy as np

import ef


# =============================================================================== fémur
def lire_femur(dossier):
    """Surface (pyvista) du fémur dans le repère anatomique, et ses repères ({nom: point}, mêmes axes). Le dossier
    contient femur.stl (étape 4) et reperes_femur.json, calculé par l'étape 6 (repères anatomiques) de CT-CORA3D :
    matrice scanner -> os (avec une symétrie pour un membre gauche), centre de la tête, points des condyles..."""
    import pyvista as pv
    cora = json.loads((dossier / "reperes_femur.json").read_text(encoding="utf-8"))
    A = np.array(cora["repere"]["scanner_vers_os"], float)
    s = pv.read(str(dossier / "femur.stl")).triangulate().clean()
    s.points = np.asarray(s.points) @ A[:3, :3].T + A[:3, 3]
    if np.linalg.det(A[:3, :3]) < 0:                         # symétrie : on remet les normales vers l'extérieur
        s = s.flip_faces() if hasattr(s, "flip_faces") else s.flip_normals()
    reperes = {k: np.array(v, float) for k, v in cora["reperes"].items()}
    return s, reperes, cora


def axe_mecanique(reperes):
    """Axe mécanique du fémur (définition du projet, CORA 3D) : du centre de la tête fémorale au milieu des points
    distaux des deux condyles. Renvoie (centre de la tête, point du genou, vecteur unitaire de la tête vers le genou)."""
    C = reperes["head_center"]
    G = 0.5 * (reperes["cond_med_dist"] + reperes["cond_lat_dist"])
    return C, G, (G - C) / np.linalg.norm(G - C)


# =============================================================================== maillage de base
def tetraedres(surface, h):
    """Maillage C3D4 : surface remaillée en triangles réguliers de taille h (pyacvd), puis TetGen (rapport rayon /
    arête ≤ 1,5, volume au plus celui d'un tétraèdre régulier d'arête h)."""
    import pyacvd
    import tetgen
    n_points = int(2 * surface.area / (np.sqrt(3) * h ** 2))
    clus = pyacvd.Clustering(surface)
    if surface.n_points < 3 * n_points:
        clus.subdivide(2)
    clus.cluster(n_points)
    peau = clus.create_mesh().clean()
    X, conn, _, _ = tetgen.TetGen(peau).tetrahedralize(quality=True, minratio=1.5, mindihedral=10.0,
                                                        maxvolume=h ** 3 / (6 * np.sqrt(2)), quiet=True)
    return orienter_tetra(np.asarray(X, float), np.asarray(conn, np.int64))


def orienter_tetra(X, conn):
    """Abaqus veut un volume positif : (x2 - x1) × (x3 - x1) · (x4 - x1) > 0 ; sinon on échange les nœuds 2 et 3."""
    a, b, c, d = (X[conn[:, k]] for k in range(4))
    neg = np.einsum("ij,ij->i", np.cross(b - a, c - a), d - a) < 0
    conn = conn.copy()
    conn[neg, 1], conn[neg, 2] = conn[neg, 2].copy(), conn[neg, 1].copy()
    return X, conn


def _fusionner(X, conn, tol=1e-6):
    """Fusionne les nœuds confondus (même position à tol près) : renvoie (X unique, connectivité renumérotée)."""
    cle = np.round(X / tol).astype(np.int64)
    _, premier, inverse = np.unique(cle, axis=0, return_index=True, return_inverse=True)
    return X[premier], inverse.ravel()[conn]


def base_courbe(surface, X, conn):
    """Géométrie figée : le maillage de base passe en tétraèdres quadratiques (C3D10) dont les nœuds milieux des arêtes
    de surface sont posés sur le STL (point le plus proche). La surface devient courbe (morceaux de surfaces du second
    degré) : c'est la « pièce », comme une géométrie de CAO dans Abaqus. Garde-fous : un nœud milieu ne bouge pas de
    plus d'un quart de son arête ; si le rapport des jacobiens (min / max) d'un élément passe sous 0,2, le déplacement
    de ses nœuds milieux est réduit de moitié, autant de fois que nécessaire."""
    X2, c10 = ef.quadratique(X, conn, "C3D10")
    faces = faces_exterieures(conn, "C3D4")
    aretes = {tuple(sorted(e)) for f in faces for e in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0]))}
    paires = np.array(ef.ELEMENTS["C3D10"].aretes)
    a_, b_ = c10[:, paires[:, 0]].ravel(), c10[:, paires[:, 1]].ravel()
    milieux = c10[:, 4:].ravel()
    sur = np.array([(min(x, y), max(x, y)) in aretes for x, y in zip(a_, b_)])
    cibles, ia, ib = milieux[sur], a_[sur], b_[sur]
    cibles, j = np.unique(cibles, return_index=True)
    _, proche = surface.find_closest_cell(X2[cibles], return_closest_point=True)
    d = proche - X2[cibles]
    L = np.linalg.norm(X2[ia[j]] - X2[ib[j]], axis=1)
    d *= np.minimum(1.0, 0.25 * L / np.maximum(np.linalg.norm(d, axis=1), 1e-12))[:, None]
    deplacement = np.zeros_like(X2)
    deplacement[cibles] = d
    el = ef.ELEMENTS["C3D10"]
    points = np.vstack([el.points, el.noeuds_ref])
    for _ in range(20):
        Y = X2 + deplacement
        dets = np.stack([np.linalg.det(np.einsum("enj,nk->ejk", Y[c10], el.dN(xi)[0])) for xi in points], 1)
        mauvais = (dets.min(1) <= 0) | (dets.min(1) < 0.2 * dets.max(1))
        if not mauvais.any():
            break
        deplacement[np.unique(c10[mauvais][:, 4:])] *= 0.5     # on réduit le déplacement de moitié, sans l'annuler
    return Y, c10


def _carte(Xe, L):
    """Transformation quadratique des tétraèdres de base : Xe (E, 10, 3) nœuds C3D10, L (E, P, 4) coordonnées
    barycentriques -> positions (E, P, 3)."""
    N = np.concatenate([L * (2 * L - 1)] + [4 * L[..., [a]] * L[..., [b]] for a, b in ef.ELEMENTS["C3D10"].aretes], -1)
    return np.einsum("epn,enj->epj", N, Xe)


_A10 = ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))


def _reseau_tetra(k):
    """Subdivision « edgewise » du tétraèdre de référence en k³ tétraèdres : points du réseau (entiers
    k ≥ x1 ≥ x2 ≥ x3 ≥ 0) et sous-tétraèdres du découpage de Freudenthal contenus dans cette région."""
    pts = [(a, b, c) for a in range(k + 1) for b in range(a + 1) for c in range(b + 1)]
    perms = [(0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)]
    tets = []
    for a in range(k):
        for b in range(k):
            for c in range(k):
                for p in perms:
                    v = [np.array((a, b, c))]
                    for ax in p:
                        w = v[-1].copy()
                        w[ax] += 1
                        v.append(w)
                    if all(k >= x[0] >= x[1] >= x[2] >= 0 for x in v):
                        tets.append(np.array(v))
    return pts, tets


def tetra_k(Xb, cb, k, quadratique=False):
    """Tétraèdres au niveau k sur la géométrie figée : chaque tétraèdre de base est coupé en k³ (subdivision
    « edgewise »), et chaque nœud est placé par la transformation quadratique de l'élément de base. Les sommets de
    chaque tétraèdre sont rangés par numéro croissant : deux voisins découpent leur face commune de la même façon
    (maillage conforme). quadratique=True : C3D10, nœuds milieux placés aussi par la transformation (arêtes courbes)."""
    K = 2 * k if quadratique else k
    pts, _ = _reseau_tetra(K)
    _, tets_k = _reseau_tetra(k)
    index = {p: i for i, p in enumerate(pts)}
    s = 2 if quadratique else 1
    conn_loc = []
    for v in tets_k:
        som = [tuple(s * x) for x in v]
        mil = [tuple(v[a] + v[b]) for a, b in _A10] if quadratique else []
        conn_loc.append([index[q] for q in som + mil])
    conn_loc = np.array(conn_loc)
    P = np.array(pts, float) / K
    w = np.c_[1 - P[:, 0], P[:, 0] - P[:, 1], P[:, 1] - P[:, 2], P[:, 2]]          # poids des sommets rangés
    ordre = np.argsort(cb[:, :4], axis=1)                                            # rang -> sommet d'origine
    L = np.zeros((len(cb), len(P), 4))
    np.put_along_axis(L, np.broadcast_to(ordre[:, None, :], L.shape), np.broadcast_to(w[None], L.shape), axis=2)
    X = _carte(Xb[cb], L).reshape(-1, 3)
    conn = (np.arange(len(cb))[:, None, None] * len(P) + conn_loc[None]).reshape(len(cb) * len(conn_loc), -1)
    X, conn = _fusionner(X, conn)
    a, b, c, d = (X[conn[:, i]] for i in range(4))
    neg = np.einsum("ij,ij->i", np.cross(b - a, c - a), d - a) < 0                  # orientation (sommets 2 <-> 3)
    perm = [0, 2, 1, 3] + ([6, 5, 4, 7, 9, 8] if quadratique else [])
    conn[neg] = conn[neg][:, perm]
    return X, conn


_C8 = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]])
_A20 = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7))


def hexa_k(Xb, cb, k, quadratique=False):
    """Hexaèdres au niveau k sur la géométrie figée : chaque tétraèdre de base est coupé en 4 hexaèdres (sommet,
    milieux des arêtes, centres des faces, centre), chacun coupé en k³ ; chaque nœud est placé par la transformation
    quadratique de l'élément de base. quadratique=True : C3D20, nœuds milieux placés aussi par la transformation."""
    K = 2 * k if quadratique else k
    t = np.linspace(-1, 1, K + 1)
    R = np.array(np.meshgrid(t, t, t, indexing="ij")).reshape(3, -1).T                # réseau (K+1)³
    N8 = ef.ELEMENTS["C3D8"].N(R)
    e = np.eye(4)
    Lh = []
    for a in range(4):                                                                # 4 hexaèdres par tétraèdre
        b, c, d = [i for i in range(4) if i != a]
        coins = np.array([e[a], (e[a] + e[b]) / 2, (e[a] + e[b] + e[c]) / 3, (e[a] + e[c]) / 2, (e[a] + e[d]) / 2,
                          (e[a] + e[b] + e[d]) / 3, np.full(4, 0.25), (e[a] + e[c] + e[d]) / 3])
        Lh.append(N8 @ coins)
    Lh = np.concatenate(Lh)                                                           # (4 (K+1)³, 4)
    idx = np.arange((K + 1) ** 3).reshape(K + 1, K + 1, K + 1)
    s = 2 if quadratique else 1
    loc = []
    for i in range(k):
        for j in range(k):
            for l in range(k):
                o = np.array([i, j, l]) * s
                som = [idx[tuple(o + s * c)] for c in _C8]
                mil = [idx[tuple(o + _C8[a] + _C8[b])] for a, b in _A20] if quadratique else []
                loc.append(som + mil)
    loc = np.array(loc)
    nP = (K + 1) ** 3
    loc4 = np.concatenate([loc + h * nP for h in range(4)])                           # 4 hexaèdres par tétraèdre
    X = _carte(Xb[cb], np.broadcast_to(Lh[None], (len(cb),) + Lh.shape)).reshape(-1, 3)
    conn = (np.arange(len(cb))[:, None, None] * (4 * nP) + loc4[None]).reshape(len(cb) * len(loc4), -1)
    X, conn = _fusionner(X, conn)
    dN = ef.ELEMENTS["C3D8"].dN(np.zeros(3))[0]
    neg = np.linalg.det(np.einsum("enj,nk->ejk", X[conn[:, :8]], dN)) < 0            # orientation : haut <-> bas
    perm = [4, 5, 6, 7, 0, 1, 2, 3] + (list(range(12, 16)) + list(range(8, 12)) + list(range(16, 20))
                                       if quadratique else [])
    conn[neg] = conn[neg][:, perm]
    return X, conn


def noeuds_peau(conn, nom):
    """Nœuds de la surface extérieure (sommets et, pour un élément quadratique, nœuds milieux des arêtes de peau)."""
    base = "C3D4" if nom in ("C3D4", "C3D10") else "C3D8"
    n_som = 4 if base == "C3D4" else 8
    faces = faces_exterieures(conn[:, :n_som], nom)
    peau = np.unique(faces)
    if nom in ef.LINEAIRE:
        el = ef.ELEMENTS[nom]
        a_, b_ = np.array(el.aretes).T
        cle = {tuple(sorted(e)) for f in faces for e in zip(f, np.roll(f, -1))}
        mil = conn[:, n_som:].ravel()
        ia, ib = conn[:, a_].ravel(), conn[:, b_].ravel()
        sur = np.array([(min(x, y), max(x, y)) in cle for x, y in zip(ia, ib)])
        peau = np.union1d(peau, mil[sur])
    return peau


FACES = {"C3D4": [(0, 1, 2), (0, 3, 1), (1, 3, 2), (2, 3, 0)],
         "C3D8": [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]}


def faces_exterieures(conn, nom):
    """Faces de bord (sommets seulement) : faces qui n'appartiennent qu'à un seul élément."""
    base = "C3D4" if nom in ("C3D4", "C3D10") else "C3D8"
    F = np.vstack([conn[:, list(f)] for f in FACES[base]])
    _, inv, nb = np.unique(np.sort(F, 1), axis=0, return_inverse=True, return_counts=True)
    return F[nb[inv.ravel()] == 1]


def qualite_hexa(X, conn):
    """Jacobien relatif minimal de chaque C3D8 (aux 8 coins) : 1 pour un cube parfait, ≤ 0 pour un élément retourné."""
    el = ef.ELEMENTS["C3D8"]
    q = np.full(len(conn), np.inf)
    for a in range(8):
        J = np.einsum("enj,nk->ejk", X[conn], el.dN(el.noeuds_ref[a])[0])
        q = np.minimum(q, np.linalg.det(J) / np.prod(np.linalg.norm(J, axis=1), axis=1))
    return q


# =============================================================================== poutre de validation
def poutre_hexa(L, b, h, m):
    """Poutre [0, L] × [0, b] × [0, h] en hexaèdres : m éléments dans l'épaisseur, autant que nécessaire ailleurs."""
    d = h / m
    nx, ny, nz = int(round(L / d)), int(round(b / d)), m
    x, y, z = np.linspace(0, L, nx + 1), np.linspace(0, b, ny + 1), np.linspace(0, h, nz + 1)
    X = np.array(np.meshgrid(x, y, z, indexing="ij")).reshape(3, -1).T
    idx = np.arange(len(X)).reshape(nx + 1, ny + 1, nz + 1)
    I, J, K = (g.ravel() for g in np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing="ij"))
    conn = np.stack([idx[I, J, K], idx[I + 1, J, K], idx[I + 1, J + 1, K], idx[I, J + 1, K],
                     idx[I, J, K + 1], idx[I + 1, J, K + 1], idx[I + 1, J + 1, K + 1], idx[I, J + 1, K + 1]], 1)
    return X, conn


def hexa_vers_tetra(X, conn):
    """Chaque hexaèdre d'une grille régulière coupé en 6 tétraèdres autour de sa diagonale 1-7 (découpage de Kuhn,
    conforme sur une grille régulière)."""
    t = [(0, 1, 2, 6), (0, 2, 3, 6), (0, 3, 7, 6), (0, 7, 4, 6), (0, 4, 5, 6), (0, 5, 1, 6)]
    return orienter_tetra(X, np.vstack([conn[:, list(q)] for q in t]))


def maillage(type_, X, conn):
    """Passe au quadratique si besoin (nœuds au milieu des arêtes droites) : type_ dans C3D4, C3D10, C3D8, C3D20."""
    return ef.quadratique(X, conn, type_) if type_ in ef.LINEAIRE else (X, conn)
