"""
etude_femur.py : étude de convergence du maillage éléments finis du fémur du lévrier, comme dans Abaqus.

Le cas de charge : appui statique (chien debout, immobile).
  géométrie  donnees/femur.stl (série hanche et genou, étape 4), dans le repère anatomique de l'étape 6 de CT-CORA3D
             (donnees/reperes_femur.json) : X latéral,
             Y proximal, Z caudal. Géométrie figée : maillage de base TetGen (h0 = 7 mm, 533 sommets), passé en
             tétraèdres quadratiques dont les nœuds milieux de surface sont sur le STL (surface courbe) ;
  matériau   élastique linéaire, homogène, isotrope : E = 17 GPa, ν = 0,3 (os cortical ; le STL est plein) ;
  charge     1/4 du poids du corps : 30 kg (standard de race du lévrier : 27 à 32 kg) × 9,81 / 4 = 73,6 N, appliquée au
             centre de la tête fémorale, dans la direction de l'axe mécanique (centre de la tête -> milieu des points
             distaux des condyles) ; elle passe par une cupule rigide liée à la tête (contrainte « Tie ») ;
  appui      encastrement des condyles (nœuds à moins de 10 mm de l'extrémité distale) ;
  résultat   contrainte de von Mises maximale aux nœuds au milieu de la diaphyse (40 à 60 % de l'axe mécanique).

Les maillages (même géométrie pour tous) :
  C3D4, C3D10   chaque tétraèdre de base coupé en k³ tétraèdres ;
  C3D8, C3D20   chaque tétraèdre de base coupé en 4 hexaèdres, puis chaque hexaèdre en k³ ;
  tous les nœuds sont placés par la transformation quadratique des tétraèdres de base : la pièce ne change pas.
Contrôle de la force : la série C3D4 est refaite avec F / 2 et 2 F.

Usage :
  python etude_femur.py              toutes les séries (reprend où il s'était arrêté)
  python etude_femur.py --inp        écrit aussi un .inp Abaqus par maillage (abaqus/femur_<élément>_k<k>.inp)
  python etude_femur.py --figures    figures seules
Sorties : resultats/convergence_femur.csv, ../images/femur_*.pdf, ../images/femur_*.png
"""
import argparse
import csv
import time
from pathlib import Path

import numpy as np

import ef
import maillages as M

ICI = Path(__file__).resolve().parent
DOSSIER_OS = ICI / "donnees"          # femur.stl et reperes_femur.json (étape 6 de CT-CORA3D)
CSV = ICI / "resultats" / "convergence_femur.csv"
IMAGES = ICI.parent / "images"

E, NU = 17000.0, 0.3            # MPa
MASSE_KG, G = 30.0, 9.81         # lévrier : standard de race 27 à 32 kg (Canadian Kennel Club)
FRACTION_POIDS = 0.25            # 1/4 du poids du corps par membre (hypothèse de l'étude, chien debout immobile)
F_N = MASSE_KG * G * FRACTION_POIDS
H0_MM = 7.0                      # taille du maillage de base (géométrie figée)
ENCASTREMENT_MM = 10.0           # condyles : nœuds à moins de 10 mm de l'extrémité distale
CUPULE_DEMI_ANGLE_DEG = 60.0     # zone de la tête liée à la cupule : calotte de 60° autour de l'axe mécanique
CUPULE_TOLERANCE_MM = 2.0        # nœud de la calotte : à moins de 2 mm de la sphère de la tête
TRANCHE = (0.40, 0.60)           # milieu de la diaphyse, en fraction de l'axe mécanique (0 = tête, 1 = genou)
SERIES = [("C3D4", 1.0, range(1, 10)), ("C3D10", 1.0, range(1, 6)), ("C3D8", 1.0, range(1, 5)),
          ("C3D20", 1.0, range(1, 3)), ("C3D4", 0.5, range(1, 8)), ("C3D4", 2.0, range(1, 8))]
CHAMPS = ["element", "k", "facteur_force", "force_N", "noeuds", "elements", "ddl", "noeuds_cupule", "volume_cm3",
          "sigma_milieu_MPa", "sigma_max_MPa", "deplacement_tete_mm", "reaction_N", "temps_s", "solveur"]
COULEURS = {"C3D4": "#c0392b", "C3D10": "#1f5f8b", "C3D8": "#b8611a", "C3D20": "#3a7d2c"}
LEGENDES = {"C3D4": "C3D4 : tétraèdre linéaire", "C3D10": "C3D10 : tétraèdre quadratique",
            "C3D8": "C3D8 : hexaèdre linéaire", "C3D20": "C3D20 : hexaèdre quadratique"}
_CACHE = {}


def modele():
    """Surface, repères, axe mécanique et maillage de base (calculés une fois)."""
    if not _CACHE:
        s, R, cora = M.lire_femur(DOSSIER_OS)
        C, Gn, u = M.axe_mecanique(R)
        _CACHE.update(surface=s, reperes=R, C=C, genou=Gn, u=u, rayon=cora["qualite"]["tete_rayon_mm"],
                      base=M.base_courbe(s, *M.tetraedres(s, H0_MM)))
    return _CACHE


def maillage_k(nom, k):
    """Maillage de l'élément `nom` au niveau k, sur la géométrie figée (courbe)."""
    m = modele()
    Xb, cb = m["base"]
    if nom in ("C3D4", "C3D10"):
        X, conn = M.tetra_k(Xb, cb, k, quadratique=(nom == "C3D10"))
    else:
        X, conn = M.hexa_k(Xb, cb, k, quadratique=(nom == "C3D20"))
    return X, conn


def zones(X, conn, nom):
    """Nœuds encastrés (condyles), nœuds liés à la cupule (calotte de la tête du côté de l'acétabulum), position de
    chaque nœud le long de l'axe mécanique (0 : centre de la tête ; 1 : genou)."""
    m = modele()
    fixes = np.nonzero(X[:, 1] < X[:, 1].min() + ENCASTREMENT_MM)[0]
    peau = M.noeuds_peau(conn, nom)
    r = X[peau] - m["C"]
    d = np.linalg.norm(r, axis=1)
    cos = (r @ -m["u"]) / np.maximum(d, 1e-9)
    cupule = peau[(np.abs(d - m["rayon"]) < CUPULE_TOLERANCE_MM) & (cos >= np.cos(np.radians(CUPULE_DEMI_ANGLE_DEG)))]
    L = np.linalg.norm(m["genou"] - m["C"])
    t = ((X - m["C"]) @ m["u"]) / L
    return fixes, cupule, t


def calculer(nom, k, facteur=1.0, ecrire_inp=False):
    t0 = time.time()
    m = modele()
    X, conn = maillage_k(nom, k)
    fixes, cupule, t = zones(X, conn, nom)
    F = facteur * F_N * m["u"]
    D = ef.elasticite(E, NU)
    K, f, vol = ef.assembler(X, conn, nom, D)
    u, info = ef.resoudre(K, f, X, fixes, tie={"esclaves": cupule, "ref": m["C"], "F": F})
    reaction = (K @ u - f).reshape(-1, 3)[fixes].sum(0)
    vm = ef.von_mises(ef.contraintes_noeuds(X, conn, nom, D, u))
    milieu = (t >= TRANCHE[0]) & (t <= TRANCHE[1])
    if ecrire_inp and facteur == 1.0:
        (ICI / "abaqus").mkdir(exist_ok=True)
        sommets = conn[:, :4] if nom in ("C3D4", "C3D10") else conn[:, :8]
        tc = ((X[sommets].mean(1) - m["C"]) @ m["u"]) / np.linalg.norm(m["genou"] - m["C"])
        ef.ecrire_inp(ICI / "abaqus" / f"femur_{nom}_k{k}.inp", X, conn, nom, E, NU, fixes, cupule, m["C"], F,
                      np.nonzero((tc >= TRANCHE[0]) & (tc <= TRANCHE[1]))[0],
                      f"Femur du levrier, appui statique (1/4 du poids), {nom}, k = {k}, {len(X)} noeuds (Seg-Maillage)")
    return {"element": nom, "k": k, "facteur_force": facteur, "force_N": round(float(np.linalg.norm(F)), 3),
            "noeuds": len(X), "elements": len(conn), "ddl": info["ddl"], "noeuds_cupule": len(cupule),
            "volume_cm3": round(vol.sum() / 1000, 3), "sigma_milieu_MPa": round(float(vm[milieu].max()), 4),
            "sigma_max_MPa": round(float(vm.max()), 3),
            "deplacement_tete_mm": round(float(np.linalg.norm(info["U_ref"])), 5),
            "reaction_N": round(float(np.linalg.norm(reaction)), 3), "temps_s": round(time.time() - t0, 1),
            "solveur": info["solveur"]}, (X, conn, u, vm, fixes, cupule)


def lire_csv():
    if not CSV.exists():
        return []
    with open(CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def etude(ecrire_inp, max_ddl):
    faits = {(r["element"], float(r["facteur_force"]), int(r["k"])) for r in lire_csv()}
    CSV.parent.mkdir(exist_ok=True)
    nouveau = not CSV.exists()
    with open(CSV, "a", newline="", encoding="utf-8") as fichier:
        w = csv.DictWriter(fichier, fieldnames=CHAMPS)
        if nouveau:
            w.writeheader()
        for nom, facteur, niveaux in SERIES:
            for k in niveaux:
                if (nom, facteur, k) in faits:
                    continue
                r, _ = calculer(nom, k, facteur, ecrire_inp)
                w.writerow(r)
                fichier.flush()
                print(f"  {nom:6s} F x {facteur:3.1f}  k = {k}  {r['noeuds']:7d} nœuds  {r['elements']:8d} éléments  "
                      f"σ milieu = {r['sigma_milieu_MPa']:7.3f} MPa  σ max = {r['sigma_max_MPa']:7.2f}  "
                      f"cupule {r['noeuds_cupule']} nœuds  réaction {r['reaction_N']:.2f} N  {r['temps_s']:6.1f} s  "
                      f"({r['solveur']})", flush=True)
                if r["ddl"] > max_ddl:
                    break


# =============================================================================== figures
def series():
    out = {}
    for r in lire_csv():
        out.setdefault((r["element"], float(r["facteur_force"])), []).append(
            (int(r["noeuds"]), int(r["elements"]), float(r["sigma_milieu_MPa"]), float(r["sigma_max_MPa"])))
    for v in out.values():
        v.sort()
    return out


def reference(S):
    """Plateau : moyenne des deux maillages quadratiques les plus fins (C3D10 et C3D20)."""
    return 0.5 * (S[("C3D10", 1.0)][-1][2] + S[("C3D20", 1.0)][-1][2])


def figures():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    from matplotlib.ticker import FuncFormatter
    avenir = Path("/System/Library/Fonts/Avenir Next.ttc")
    if avenir.exists():
        fm.fontManager.addfont(str(avenir))
    plt.rcParams.update({"font.family": ["Avenir Next", "DejaVu Sans"], "font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False, "savefig.bbox": "tight", "pdf.fonttype": 42})
    S = series()
    ref = reference(S)
    virgule = lambda x, n=2: f"{x:.{n}f}".replace(".", ",")
    milliers = FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v >= 1000 else f"{v:.0f}")
    ordre = ("C3D4", "C3D10", "C3D8", "C3D20")

    def sauver(fig, nom):
        fig.savefig(IMAGES / f"{nom}.pdf")
        fig.savefig(ICI / "resultats" / f"{nom}.png", dpi=150)
        plt.close(fig)
        print("  figure", nom)

    # 1. courbe de convergence, échelle linéaire : en nœuds et en éléments
    xmax = {0: max(p[0] for v in S.values() for p in v) * 1.05, 1: max(p[1] for v in S.values() for p in v) * 1.05}
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.9), sharey=True)
    for ax, col, titre in ((axes[0], 0, "nombre de nœuds"), (axes[1], 1, "nombre d'éléments")):
        ax.axhspan(ref * 0.99, ref * 1.01, color="#3a7d2c", alpha=0.10, lw=0)
        ax.axhline(ref, color="#555555", ls=":", lw=1)
        for el in ordre:
            if (el, 1.0) in S:
                v = S[(el, 1.0)]
                ax.plot([p[col] for p in v], [p[2] for p in v], "o-", color=COULEURS[el], label=LEGENDES[el], ms=4.5,
                        lw=1.7)
        ax.set_xlim(0, xmax[col])
        ax.xaxis.set_major_formatter(milliers)
        ax.set_xlabel(titre)
        ax.grid(True, color="#e5e5e5", lw=0.6)
        ax.annotate("zone de convergence (< 1 % d'écart)", xy=(0.97, ref * 1.012), xycoords=("axes fraction", "data"),
                    ha="right", va="bottom", fontsize=8, color="#3a7d2c")
    axes[0].set_ylabel("σ von Mises max au milieu de la diaphyse (MPa)")
    axes[1].legend(frameon=False, loc="lower right", fontsize=8)
    fig.suptitle(f"Fémur, appui statique (F = {virgule(F_N, 1)} N sur la tête, axe mécanique) : plateau "
                 f"{virgule(ref)} MPa", fontsize=10)
    sauver(fig, "femur_convergence")

    # 2. échelle logarithmique et écart au plateau
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.6))
    for el in ordre:
        if (el, 1.0) in S:
            v = S[(el, 1.0)]
            axes[0].plot([p[0] for p in v], [p[2] for p in v], "o-", color=COULEURS[el], label=LEGENDES[el], ms=4.5,
                         lw=1.7)
            axes[1].plot([p[0] for p in v], [max(100 * abs(p[2] / ref - 1), 1e-3) for p in v], "o-",
                         color=COULEURS[el], ms=4.5, lw=1.7)
    axes[0].axhspan(ref * 0.99, ref * 1.01, color="#3a7d2c", alpha=0.10, lw=0)
    axes[0].set_ylabel("σ von Mises max (MPa)")
    axes[1].axhline(1, color="#3a7d2c", ls="--", lw=1)
    axes[1].text(0.99, 1.1, "1 %", transform=axes[1].get_yaxis_transform(), ha="right", fontsize=8, color="#3a7d2c")
    axes[1].set_yscale("log")
    axes[1].set_ylabel("écart au plateau (%)")
    for ax in axes:
        ax.set_xscale("log")
        ax.set_xlabel("nombre de nœuds")
        ax.grid(True, which="both", color="#e5e5e5", lw=0.6)
    axes[0].legend(frameon=False, loc="lower right", fontsize=8)
    sauver(fig, "femur_log")

    # 3. effet de la force (C3D4 avec F / 2, F, 2 F)
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.6))
    teintes = {0.5: "#e8a39a", 1.0: "#c0392b", 2.0: "#6e1d14"}
    for fac in (0.5, 1.0, 2.0):
        if ("C3D4", fac) in S:
            v = [p for p in S[("C3D4", fac)] if fac != 1.0 or p[0] <= max(q[0] for q in S[("C3D4", 0.5)])]
            n = [p[0] for p in v]
            axes[0].plot(n, [p[2] for p in v], "o-", color=teintes[fac], ms=4.5, lw=1.7,
                         label=f"F = {virgule(fac * F_N, 1)} N")
            axes[1].plot(n, [p[2] / fac for p in v], "o-" if fac == 1.0 else "x--", color=teintes[fac], ms=5, lw=1.4,
                         label=f"σ × {virgule(1 / fac, 1)}")
    axes[0].set_ylabel("σ von Mises max, C3D4 (MPa)")
    axes[1].set_ylabel(f"σ ramenée à F = {virgule(F_N, 1)} N (MPa)")
    for ax in axes:
        ax.set_xscale("log")
        ax.set_xlabel("nombre de nœuds")
        ax.grid(True, which="both", color="#e5e5e5", lw=0.6)
        ax.legend(frameon=False, loc="lower right", fontsize=8)
    sauver(fig, "femur_force")

    # 4. maximum sur tout l'os (singularités au bord de la cupule et de l'encastrement)
    fig, ax = plt.subplots(figsize=(6.3, 3.4))
    for el in ordre:
        if (el, 1.0) in S:
            v = S[(el, 1.0)]
            ax.plot([p[0] for p in v], [p[3] for p in v], "o-", color=COULEURS[el], label=LEGENDES[el], ms=4.5, lw=1.7)
    ax.set_xscale("log")
    ax.set_xlabel("nombre de nœuds")
    ax.set_ylabel("σ von Mises max sur tout l'os (MPa)")
    ax.grid(True, which="both", color="#e5e5e5", lw=0.6)
    ax.legend(frameon=False, loc="upper left", fontsize=8)
    sauver(fig, "femur_max")


def carte_contraintes(nom="C3D10", k=3):
    """Rendu de la contrainte de von Mises sur la surface du fémur (vue caudale et vue médiale), échelle 0 à 3 MPa."""
    import pyvista as pv
    from PIL import Image
    pv.OFF_SCREEN = True
    _, (X, conn, u, vm, fixes, cupule) = calculer(nom, k)
    sommets = conn[:, :4] if nom in ("C3D4", "C3D10") else conn[:, :8]
    n_som = np.unique(sommets)
    typ = pv.CellType.TETRA if sommets.shape[1] == 4 else pv.CellType.HEXAHEDRON
    g = pv.UnstructuredGrid(np.hstack([np.full((len(sommets), 1), sommets.shape[1]), sommets]).ravel(),
                            np.full(len(sommets), typ, np.uint8), X)
    g.point_data["von Mises (MPa)"] = vm
    peau = g.extract_surface()
    vues = []
    for nom_vue, cam in (("caudale", "xy"), ("médiale", "yz")):
        pl = pv.Plotter(off_screen=True, window_size=(900, 1600))
        pl.set_background("white")
        pl.add_mesh(peau, scalars="von Mises (MPa)", cmap="turbo", clim=[0, 3], show_scalar_bar=nom_vue == "médiale",
                    scalar_bar_args={"title": "von Mises (MPa)", "color": "black", "vertical": True,
                                     "position_x": 0.82, "position_y": 0.25, "height": 0.5})
        pl.add_points(X[cupule], color="white", point_size=4, render_points_as_spheres=True)
        pl.add_points(X[np.intersect1d(fixes, n_som)], color="#444444", point_size=3, render_points_as_spheres=True)
        if cam == "xy":
            pl.view_xy()
        else:
            pl.view_yz(negative=True)
        pl.camera.up = (0, 1, 0)
        pl.reset_camera()
        pl.camera.zoom(1.25)
        im = Image.fromarray(pl.screenshot(return_img=True))
        pl.close()
        fond = np.asarray(im.convert("L")) < 250
        lig, col = np.nonzero(fond.any(1))[0], np.nonzero(fond.any(0))[0]
        vues.append(im.crop((max(col[0] - 10, 0), max(lig[0] - 10, 0), col[-1] + 10, lig[-1] + 10)))
    H = max(v.height for v in vues)
    image = Image.new("RGB", (sum(v.width for v in vues) + 60, H), "white")
    x = 0
    for v in vues:
        image.paste(v, (x, (H - v.height) // 2))
        x += v.width + 60
    image.save(IMAGES / "femur_contraintes.png")
    print("  images/femur_contraintes.png")


def images_maillages():
    """Le fémur à géométrie figée en C3D4 (k = 1, 2, 4) et en C3D8 (k = 1, 2) : ../images/femur_maillages.png."""
    import pyvista as pv
    from PIL import Image
    pv.OFF_SCREEN = True
    vues = []
    for nom, k in (("C3D4", 1), ("C3D4", 2), ("C3D4", 4), ("C3D8", 1), ("C3D8", 2)):
        X, conn = maillage_k(nom, k)
        typ = pv.CellType.TETRA if nom == "C3D4" else pv.CellType.HEXAHEDRON
        n = conn.shape[1]
        g = pv.UnstructuredGrid(np.hstack([np.full((len(conn), 1), n), conn]).ravel(), np.full(len(conn), typ, np.uint8), X)
        pl = pv.Plotter(off_screen=True, window_size=(700, 1500))
        pl.set_background("white")
        pl.add_mesh(g.extract_surface(), color="#efe6d2", show_edges=True, edge_color="#5b4a2e", line_width=0.5)
        pl.view_xy()
        pl.camera.up = (0, 1, 0)
        pl.reset_camera()
        pl.camera.zoom(1.3)
        im = Image.fromarray(pl.screenshot(return_img=True))
        pl.close()
        fond = np.asarray(im.convert("L")) < 250
        lig, col = np.nonzero(fond.any(1))[0], np.nonzero(fond.any(0))[0]
        vues.append(im.crop((max(col[0] - 8, 0), max(lig[0] - 8, 0), col[-1] + 8, lig[-1] + 8)))
        print(f"  {nom} k = {k} : {len(X)} nœuds, {len(conn)} éléments")
    H = max(v.height for v in vues)
    image = Image.new("RGB", (sum(v.width for v in vues) + 40 * (len(vues) - 1), H), "white")
    x = 0
    for v in vues:
        image.paste(v, (x, (H - v.height) // 2))
        x += v.width + 40
    image.save(IMAGES / "femur_maillages.png")
    print("  images/femur_maillages.png")


if __name__ == "__main__":
    a = argparse.ArgumentParser(description="Étude de convergence du fémur (appui statique)")
    a.add_argument("--inp", action="store_true", help="écrire les fichiers Abaqus (.inp)")
    a.add_argument("--max-ddl", type=int, default=1_400_000)
    a.add_argument("--figures", action="store_true")
    x = a.parse_args()
    if not x.figures:
        etude(x.inp, x.max_ddl)
    figures()
    carte_contraintes()
    images_maillages()
