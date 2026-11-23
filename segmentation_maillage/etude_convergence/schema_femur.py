"""
schema_femur.py : schéma draw.io du cas de charge du fémur (modifiable dans draw.io).

Le fond est la silhouette du vrai fémur (STL du projet, vue caudale : X latéral vers la droite, Y proximal vers le
haut), intégrée comme image ; par-dessus, en éléments draw.io modifiables : axe mécanique, force F, cupule rigide et
contrainte Tie, point de référence RP, encastrement des condyles, zone mesurée, axes du repère.
Usage : python schema_femur.py   (écrit ../schemas/femur_chargement.drawio et l'exporte en ../images/schema_femur_chargement.pdf ;
        draw.io doit être fermé pendant l'export)
"""
import base64
import io
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

import etude_femur as EF

ICI = Path(__file__).resolve().parent
SCHEMAS = ICI.parent / "schemas"
DRAWIO = "/Applications/draw.io.app/Contents/MacOS/draw.io"
ECHELLE = 2.6                    # pixels par millimètre
MARGE = 30                       # pixels autour de l'os dans l'image
X0, Y0 = 260, 150                # position de l'image sur la page draw.io
POLICE = "Helvetica"


def silhouette():
    """Image PNG (transparente) de l'os vu de derrière, éclairée par l'orientation des triangles ; renvoie
    (octets PNG, largeur, hauteur, fonction mm -> pixels de l'image)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    s = EF.modele()["surface"]
    P = np.asarray(s.points)
    F = s.faces.reshape(-1, 4)[:, 1:]
    T = P[F]
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    ordre = np.argsort(T[:, :, 2].mean(1))                  # vue de derrière (+Z) : on peint du plus loin au plus proche
    lum = 0.55 + 0.45 * np.abs(n[ordre, 2]) * 0.8 + 0.2 * np.clip(n[ordre, 1], 0, 1)
    base = np.array([0.937, 0.902, 0.824])
    couleurs = np.clip(base[None] * lum[:, None], 0, 1)
    xmin, xmax, ymin, ymax = P[:, 0].min(), P[:, 0].max(), P[:, 1].min(), P[:, 1].max()
    W = int(round((xmax - xmin) * ECHELLE + 2 * MARGE))
    H = int(round((ymax - ymin) * ECHELLE + 2 * MARGE))
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(xmin - MARGE / ECHELLE, xmax + MARGE / ECHELLE)
    ax.set_ylim(ymin - MARGE / ECHELLE, ymax + MARGE / ECHELLE)
    ax.add_collection(PolyCollection(T[ordre][:, :, :2], facecolors=couleurs, edgecolors=couleurs, linewidths=0.2))
    ax.set_axis_off()
    tampon = io.BytesIO()
    fig.savefig(tampon, format="png", transparent=True, dpi=100)
    plt.close(fig)
    vers_px = lambda p: (X0 + (p[0] - (xmin - MARGE / ECHELLE)) * ECHELLE, Y0 + ((ymax + MARGE / ECHELLE) - p[1]) * ECHELLE)
    return tampon.getvalue(), W, H, vers_px


class Schema:
    def __init__(self):
        self.cellules, self.n = [], 1

    def _id(self):
        self.n += 1
        return f"c{self.n}"

    def image(self, x, y, l, h, png):
        i = self._id()
        donnees = base64.b64encode(png).decode("ascii")
        style = f"shape=image;verticalLabelPosition=bottom;aspect=fixed;imageAspect=0;image=data:image/png,{donnees};"
        self.cellules.append(f'<mxCell id="{i}" value="" style="{style}" vertex="1" parent="1">'
                             f'<mxGeometry x="{x:.1f}" y="{y:.1f}" width="{l}" height="{h}" as="geometry"/></mxCell>')

    def texte(self, x, y, l, h, t, taille=13, couleur="#222222", align="left", gras=False):
        i = self._id()
        style = (f"text;html=1;whiteSpace=wrap;fontFamily={POLICE};fontSize={taille};align={align};verticalAlign=middle;"
                 f"fontColor={couleur};" + ("fontStyle=1;" if gras else ""))
        self.cellules.append(f'<mxCell id="{i}" value="{escape(t, {chr(34): "&quot;"})}" style="{style}" vertex="1" '
                             f'parent="1"><mxGeometry x="{x:.1f}" y="{y:.1f}" width="{l}" height="{h}" as="geometry"/>'
                             f'</mxCell>')

    def forme(self, x, y, l, h, style, t=""):
        i = self._id()
        self.cellules.append(f'<mxCell id="{i}" value="{escape(t)}" style="{style}" vertex="1" parent="1">'
                             f'<mxGeometry x="{x:.1f}" y="{y:.1f}" width="{l:.1f}" height="{h:.1f}" as="geometry"/></mxCell>')

    def ligne(self, p, q, style, points=()):
        i = self._id()
        pts = "".join(f'<mxPoint x="{a:.1f}" y="{b:.1f}"/>' for a, b in points)
        tableau = f'<Array as="points">{pts}</Array>' if points else ""
        self.cellules.append(f'<mxCell id="{i}" value="" style="{style}" edge="1" parent="1"><mxGeometry relative="1" '
                             f'as="geometry"><mxPoint x="{p[0]:.1f}" y="{p[1]:.1f}" as="sourcePoint"/>'
                             f'<mxPoint x="{q[0]:.1f}" y="{q[1]:.1f}" as="targetPoint"/>{tableau}</mxGeometry></mxCell>')

    def ecrire(self, chemin):
        xml = ('<mxfile host="Seg-Maillage"><diagram id="d" name="femur_chargement"><mxGraphModel grid="0" page="0">'
               '<root><mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(self.cellules) +
               '</root></mxGraphModel></diagram></mxfile>')
        chemin.write_text(xml, encoding="utf-8")


def main():
    m = EF.modele()
    png, W, H, px = silhouette()
    C, Gn, u = m["C"], m["genou"], m["u"]
    R = m["rayon"]
    s = Schema()
    s.image(X0, Y0, W, H, png)
    virgule = lambda x, n=1: f"{x:.{n}f}".replace(".", ",")
    # axe mécanique (projection dans le plan frontal), prolongé un peu au-delà des deux extrémités
    a, b = px(C - u * 40), px(Gn + u * 12)
    s.ligne(a, b, "endArrow=none;html=1;strokeColor=#1f5f8b;strokeWidth=2;dashed=1;dashPattern=10 5;")
    lab = px(C + u * 0.22 * np.linalg.norm(Gn - C))
    s.texte(lab[0] - 238, lab[1] - 22, 200, 44, "<b>axe mécanique</b><br>centre de la tête → milieu des condyles",
            12, "#1f5f8b", align="right")
    s.ligne((lab[0] - 34, lab[1]), (lab[0] - 3, lab[1]), "endArrow=oval;endFill=1;endSize=5;html=1;"
            "strokeColor=#1f5f8b;strokeWidth=1.2;")
    # zone mesurée : 40 à 60 % de l'axe mécanique
    L = np.linalg.norm(Gn - C)
    for t in EF.TRANCHE:
        p = C + u * (t * L)
        q = px(p)
        s.ligne((q[0] - 38, q[1]), (q[0] + 38, q[1]), "endArrow=none;html=1;strokeColor=#3a7d2c;strokeWidth=2;")
    q4, q6 = px(C + u * (EF.TRANCHE[0] * L)), px(C + u * (EF.TRANCHE[1] * L))
    Pt = np.asarray(m["surface"].points)
    yb = sorted([(C + u * (t * L))[1] for t in EF.TRANCHE])
    xd = px([Pt[(Pt[:, 1] > yb[0]) & (Pt[:, 1] < yb[1]), 0].max(), 0])[0] + 14
    s.forme(xd, q4[1], 12, q6[1] - q4[1], "shape=curlyBracket;whiteSpace=wrap;html=1;rounded=1;flipH=1;"
            "strokeColor=#3a7d2c;strokeWidth=2;")
    s.texte(xd + 18, (q4[1] + q6[1]) / 2 - 26, 175, 52,
            "<b>zone mesurée</b><br>40 à 60 % de l'axe mécanique<br>(σ von Mises max)", 12, "#3a7d2c")
    # cupule rigide : arc de cercle autour de la tête, du côté de l'acétabulum (± 60° autour de -u)
    e = -u[:2] / np.linalg.norm(u[:2])
    ang0 = np.arctan2(e[1], e[0])
    arc = [px(C + (R + 3.0) * np.r_[np.cos(ang0 + a_), np.sin(ang0 + a_), 0])
           for a_ in np.radians(np.linspace(-EF.CUPULE_DEMI_ANGLE_DEG - 8, EF.CUPULE_DEMI_ANGLE_DEG + 8, 15))]
    s.ligne(arc[0], arc[-1], "endArrow=none;html=1;strokeColor=#555555;strokeWidth=6;curved=1;", points=arc[1:-1])
    # point de référence RP au centre de la tête
    rp = px(C)
    s.forme(rp[0] - 6, rp[1] - 6, 12, 12, "ellipse;whiteSpace=wrap;html=1;fillColor=#c0392b;strokeColor=#ffffff;"
            "strokeWidth=2;")
    s.texte(rp[0] - 270, rp[1] + 16, 190, 36, "<b>RP</b> : point de référence<br>(centre de la tête fémorale)", 12,
            "#c0392b", align="right")
    s.ligne((rp[0] - 76, rp[1] + 32), (rp[0] - 6, rp[1] + 4), "endArrow=none;html=1;strokeColor=#c0392b;strokeWidth=1;")
    # force F, dans la direction de l'axe mécanique, qui arrive sur la cupule
    debut, fin = px(C - u * (R + 38)), px(C - u * (R + 5))
    s.ligne(debut, fin, "endArrow=block;endFill=1;endSize=10;html=1;strokeColor=#c0392b;strokeWidth=4;")
    s.texte(debut[0] - 245, debut[1] - 8, 235, 58,
            f"<b>F = {virgule(EF.F_N)} N</b><br>¼ du poids du corps ({virgule(EF.MASSE_KG, 0)} kg × 9,81 / 4),<br>"
            "dans la direction de l'axe mécanique", 12, "#c0392b", align="right")
    # contrainte Tie
    tie = arc[len(arc) // 2 + 4]
    s.texte(tie[0] + 40, tie[1] - 66, 230, 56, "<b>cupule rigide</b> liée à la tête<br>par une <b>contrainte Tie</b>"
            "<br>(calotte de ± 60° autour de l'axe)", 12, "#555555")
    s.ligne((tie[0] + 42, tie[1] - 30), (tie[0] + 4, tie[1] - 4),
            "endArrow=oval;endFill=1;endSize=5;html=1;strokeColor=#555555;strokeWidth=1.2;")
    # encastrement des condyles
    P = np.asarray(m["surface"].points)
    bas = P[P[:, 1] < P[:, 1].min() + EF.ENCASTREMENT_MM]
    g, d = px([bas[:, 0].min(), P[:, 1].min()]), px([bas[:, 0].max(), P[:, 1].min()])
    niveau = px([0, P[:, 1].min() + EF.ENCASTREMENT_MM])[1]
    s.ligne((g[0] - 18, niveau), (d[0] + 18, niveau), "endArrow=none;html=1;strokeColor=#444444;strokeWidth=1.5;"
            "dashed=1;")
    s.forme(g[0] - 18, g[1] + 3, d[0] - g[0] + 36, 16, "rounded=0;whiteSpace=wrap;html=1;fillColor=#666666;"
            "fillStyle=hatch;strokeColor=#444444;")
    s.texte(d[0] + 26, niveau - 8, 220, 44, "<b>encastrement des condyles</b><br>nœuds à moins de 10 mm de "
            "l'extrémité distale", 12, "#444444")
    # repère et titre
    ox, oy = X0 - 150, Y0 + H - 40
    s.ligne((ox, oy), (ox + 55, oy), "endArrow=block;endFill=1;html=1;strokeColor=#333333;strokeWidth=2;")
    s.ligne((ox, oy), (ox, oy - 55), "endArrow=block;endFill=1;html=1;strokeColor=#333333;strokeWidth=2;")
    s.texte(ox + 58, oy - 10, 90, 20, "X latéral", 12)
    s.texte(ox - 10, oy - 80, 110, 20, "Y proximal", 12)
    s.texte(ox - 30, oy + 8, 220, 36, "vue caudale (plan frontal) ;<br>Z caudal vers l'observateur", 11, "#666666")
    s.texte(X0 - 230, 10, W + 520, 30, "Fémur du lévrier : appui statique sur un membre (¼ du poids du corps)", 15,
            gras=True, align="center")
    chemin = SCHEMAS / "femur_chargement.drawio"
    s.ecrire(chemin)
    print("  ", chemin.name)
    sortie = ICI.parent / "images" / "schema_femur_chargement.pdf"
    subprocess.run([DRAWIO, "--export", "--format", "pdf", "--crop", "--output", str(sortie), str(chemin)],
                   check=False, capture_output=True)
    print("  ", sortie.name, "(export draw.io)" if sortie.exists() else "(export impossible : draw.io est-il ouvert ?)")


if __name__ == "__main__":
    main()
