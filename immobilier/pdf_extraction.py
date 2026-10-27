"""
Extraction automatique depuis un plan de lotissement exporte en PDF
vectoriel (CAD/GIS) : les lots numerotes (rectangle + numero) d'une part,
et - quand le PDF le permet - la position geographique exacte du plan
d'autre part.

## Lots numerotes

Sur un plan CAD bien forme, chaque parcelle est deja dessinee comme une
forme fermee independante - pymupdf la restitue comme un objet "drawing"
avec son propre rectangle englobant exact (verifie empiriquement sur un
vrai plan : chaque cellule est tracee en "fill" + "stroke", les deux
partageant le meme rectangle englobant) - et son numero est un objet texte
separe positionne a l'interieur. On associe donc simplement chaque
rectangle dessine au (seul) libelle purement numerique dont le centre
tombe dedans : pas de reconstruction de grille necessaire.

Limites assumees : tout rectangle sans correspondance claire a EXACTEMENT
un numero est ignore plutot que devine - il reste a tracer manuellement
cote admin.

## Zones nommees (espaces verts, equipements publics, mosquees...)

Ces zones irregulieres ne deviennent jamais des lots/Bien vendables (pas
de numero), mais sont extraites comme formes purement visuelles/
informatives pour que le plan affiche sur la carte admin corresponde
fidelement au document source. Meme principe que les lots : chaque zone
est une forme fermee independante, son nom est un ou plusieurs mots-texte
proches positionnes dedans - sauf que son contour n'est pas un simple
rectangle (ex: "Espace vert" en forme d'eventail), donc on trace le
polygone exact (la suite ordonnee de segments de ligne du dessin) plutot
que de se contenter de son rectangle englobant.

## Position geographique (GeoPDF)

Un PDF exporte depuis un logiciel SIG (ex: Esri ArcMap "Export Map" avec
georeferencement active) embarque une extension standard ISO 32000
(/Measure /GEO) associant des points de la page a de vraies coordonnees
GPS. Quand elle est presente, on s'en sert pour calculer automatiquement
le centre/l'echelle/la rotation du plan - sans aucune saisie manuelle de
l'admin, meme pour le tout premier plan d'un quartier. Un PDF plat
classique (sans cette extension) n'a aucune donnee GPS : dans ce cas la
fonction retourne None et l'admin doit positionner le plan manuellement
une fois (voir PlanQuartierSerializer).
"""

import math
import re

import pymupdf

AIRE_MIN_PT2 = 15.0  # ignore les formes degenerees (bruit, traits quasi nuls)
METRES_PAR_DEGRE_LAT = 111320.0


def extraire_lots(pdf_bytes: bytes) -> list[dict]:
    """
    Retourne une liste de {"numero_lot": str, "polygone_local": [{"x","y"}, ...x4]}
    avec x,y en fraction (0..1) de la page PDF, origine (0,0) = coin haut-gauche
    (meme convention que l'image PNG rendue depuis la meme page).

    Deduplique automatiquement les numeros de lot en double (garde la
    premiere occurrence) pour rester compatible avec la contrainte
    d'unicite (plan, numero_lot) de LotDetecte, meme si aucun doublon n'a
    ete observe sur le plan de reference utilise pour concevoir ceci.
    """
    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = document.load_page(0)
        largeur_page = page.rect.width
        hauteur_page = page.rect.height
        if not largeur_page or not hauteur_page:
            return []

        rectangles = _rectangles_uniques(page)
        libelles_disponibles = _libelles_numeriques(page)

        lots = []
        numeros_vus = set()
        for rect in rectangles:
            dans_rect = [
                (cx, cy, texte)
                for cx, cy, texte in libelles_disponibles
                if rect.x0 <= cx <= rect.x1 and rect.y0 <= cy <= rect.y1
            ]
            if len(dans_rect) != 1:
                continue
            cx, cy, numero = dans_rect[0]
            libelles_disponibles.remove((cx, cy, numero))
            if numero in numeros_vus:
                continue
            numeros_vus.add(numero)

            polygone_local = [
                {"x": rect.x0 / largeur_page, "y": rect.y0 / hauteur_page},
                {"x": rect.x1 / largeur_page, "y": rect.y0 / hauteur_page},
                {"x": rect.x1 / largeur_page, "y": rect.y1 / hauteur_page},
                {"x": rect.x0 / largeur_page, "y": rect.y1 / hauteur_page},
            ]
            lots.append({"numero_lot": numero, "polygone_local": polygone_local})
        return lots
    finally:
        document.close()


def extraire_zones(pdf_bytes: bytes) -> list[dict]:
    """
    Retourne une liste de {"nom": str, "type_zone": str, "polygone_local": [{"x","y"}, ...]}
    pour chaque zone nommee (espace vert, equipement public, mosquee...)
    detectee sur la page, meme convention fraction-de-page que extraire_lots.
    """
    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = document.load_page(0)
        largeur_page = page.rect.width
        hauteur_page = page.rect.height
        if not largeur_page or not hauteur_page:
            return []

        libelles = _libelles_zones(page)
        drawings = page.get_drawings()

        zones = []
        for texte, cx, cy in libelles:
            candidats = [
                d for d in drawings
                if d["rect"].x0 <= cx <= d["rect"].x1 and d["rect"].y0 <= cy <= d["rect"].y1
                and d["rect"].width * d["rect"].height >= AIRE_MIN_PT2
            ]
            if not candidats:
                continue
            # La plus petite forme contenant le libelle : evite de remonter
            # jusqu'au cadre de la page (qui "contient" tout).
            meilleure = min(candidats, key=lambda d: d["rect"].width * d["rect"].height)

            sommets = _tracer_polygone(meilleure)
            if len(sommets) < 3:
                continue

            polygone_local = [{"x": px / largeur_page, "y": py / hauteur_page} for px, py in sommets]
            zones.append({"nom": texte, "type_zone": _type_zone(texte), "polygone_local": polygone_local})
        return zones
    finally:
        document.close()


def _libelles_zones(page):
    """
    Regroupe les mots-texte non-numeriques proches sur une meme ligne en
    libelles complets (ex: les 3 mots "Equipement"/"public"/"B" -> une
    seule zone "Equipement public B"), et retourne (texte, centre_x, centre_y).
    """
    mots = [
        (x0, y0, x1, y1, texte.strip())
        for x0, y0, x1, y1, texte, *_ in page.get_text("words")
        if re.match(r"^[A-Za-z0-9]+$", texte.strip()) and not texte.strip().isdigit()
    ]
    mots.sort(key=lambda m: (round(m[1]), m[0]))

    groupes = []
    courant = None
    for mot in mots:
        if courant and abs(mot[1] - courant[-1][1]) < 3 and (mot[0] - courant[-1][2]) < 30:
            courant.append(mot)
        else:
            courant = [mot]
            groupes.append(courant)

    libelles = []
    for groupe in groupes:
        texte = " ".join(m[4] for m in groupe)
        x0 = min(m[0] for m in groupe)
        y0 = min(m[1] for m in groupe)
        x1 = max(m[2] for m in groupe)
        y1 = max(m[3] for m in groupe)
        libelles.append((texte, (x0 + x1) / 2, (y0 + y1) / 2))
    return libelles


def _tracer_polygone(drawing):
    """
    Reconstruit les sommets ordonnes d'un contour ferme a partir des
    segments de ligne ("l") d'un drawing pymupdf, dans leur ordre de
    tracage (verifie empiriquement continu : la fin de chaque segment
    correspond au debut du suivant). Les items non-"l" (quads, courbes)
    sont ignores - non rencontres en pratique sur les zones testees.
    """
    return [(item[1].x, item[1].y) for item in drawing["items"] if item[0] == "l"]


def _type_zone(texte):
    minuscule = texte.lower()
    if minuscule.startswith("espace vert"):
        return "espace_vert"
    if minuscule.startswith("espace pub"):
        return "espace_public"
    if minuscule.startswith("equipement"):
        return "equipement_public"
    if minuscule.startswith("mosquee"):
        return "mosquee"
    return "autre"


def extraire_position(pdf_bytes: bytes) -> dict | None:
    """
    Si le PDF contient une georeference GeoPDF (/Measure /GEO, ex: export
    ArcMap), retourne {"centre_latitude", "centre_longitude", "largeur_m",
    "hauteur_m", "rotation_deg"} calcule a partir des points de controle
    embarques. Retourne None si absent ou illisible (PDF plat classique).
    """
    document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = document.load_page(0)
        points = _points_controle_geopdf(document, page)
        if points is None or len(points) < 3:
            return None
        return _position_depuis_points_controle(points)
    except Exception:
        # Best-effort : toute anomalie de parsing retombe simplement sur
        # le calibrage manuel existant, jamais une erreur bloquante.
        return None
    finally:
        document.close()


def _rectangles_uniques(page, aire_min=AIRE_MIN_PT2):
    """
    Rectangle englobant de chaque forme dessinee sur la page, deduplique
    (une meme parcelle est generalement tracee deux fois : un remplissage
    et un contour, avec le meme rectangle englobant).
    """
    vus = set()
    rects = []
    for drawing in page.get_drawings():
        r = drawing["rect"]
        if r.width <= 0 or r.height <= 0 or r.width * r.height < aire_min:
            continue
        cle = (round(r.x0), round(r.y0), round(r.x1), round(r.y1))
        if cle in vus:
            continue
        vus.add(cle)
        rects.append(r)
    return rects


def _libelles_numeriques(page):
    """Liste de (centre_x, centre_y, texte) pour chaque mot purement numerique de la page."""
    libelles = []
    for x0, y0, x1, y1, texte, *_ in page.get_text("words"):
        texte = texte.strip()
        if texte.isdigit():
            libelles.append(((x0 + x1) / 2, (y0 + y1) / 2, texte))
    return libelles


def _points_controle_geopdf(document, page):
    """
    Cherche un dictionnaire /Measure /GEO rattache a la page (extension
    GeoPDF ISO 32000, telle qu'exportee par Esri ArcMap) et retourne une
    liste de points de controle (fraction_x, fraction_y, lat, lng), avec
    fraction_x/y dans [0,1] en convention haut-gauche (meme repere que
    extraire_lots). None si l'extension est absente ou mal formee.

    pymupdf n'offre pas d'API haut niveau pour cette extension rare : on
    lit donc le dictionnaire PDF brut de la page (xref_object), qui reste
    en coordonnees PDF natives (origine bas-gauche, y vers le haut) -
    d'ou la conversion manuelle vers notre convention haut-gauche.
    """
    page_dict = document.xref_object(page.xref)
    vp_match = re.search(r"/VP\s*\[\s*<<(.*?)>>\s*\]", page_dict, re.DOTALL)
    if not vp_match:
        return None
    vp_body = vp_match.group(1)

    bbox_match = re.search(r"/BBox\s*\[([^\]]+)\]", vp_body)
    measure_match = re.search(r"/Measure\s+(\d+)\s+\d+\s+R", vp_body)
    if not bbox_match or not measure_match:
        return None

    bx0, by0, bx1, by1 = (float(v) for v in bbox_match.group(1).split())
    measure_dict = document.xref_object(int(measure_match.group(1)))
    if "/GEO" not in measure_dict:
        return None

    gpts_match = re.search(r"/GPTS\s*\[([^\]]+)\]", measure_dict)
    lpts_match = re.search(r"/LPTS\s*\[([^\]]+)\]", measure_dict)
    if not gpts_match or not lpts_match:
        return None

    gpts = [float(v) for v in gpts_match.group(1).split()]
    lpts = [float(v) for v in lpts_match.group(1).split()]
    if len(gpts) < 6 or len(gpts) != len(lpts):
        return None

    largeur_page, hauteur_page = page.rect.width, page.rect.height
    points = []
    for i in range(0, len(lpts) - 1, 2):
        lx, ly = lpts[i], lpts[i + 1]
        lat, lng = gpts[i], gpts[i + 1]
        # BBox : deux coins de reference en coordonnees PDF natives
        # (origine bas-gauche) ; LPTS interpole linearement entre eux.
        px = bx0 + lx * (bx1 - bx0)
        py = by0 + ly * (by1 - by0)
        # Conversion vers notre convention haut-gauche (celle de get_text/
        # get_drawings et donc de extraire_lots).
        fx = px / largeur_page
        fy = (hauteur_page - py) / hauteur_page
        points.append((fx, fy, lat, lng))
    return points


def _position_depuis_points_controle(points):
    """
    Ajuste une transformation affine (fraction_page -> lat/lng) sur 3 des
    points de controle (une projection cartographique sur une zone aussi
    petite qu'un quartier est affine a quelques dizaines de cm pres - le
    4eme point sert naturellement de verification informelle en dev, pas
    necessaire en prod), puis en deduit centre/largeur/hauteur/rotation
    du plan - exactement les champs manuels de PlanQuartier.
    """
    matrice = [[fx, fy, 1] for fx, fy, _, _ in points[:3]]
    lats = [lat for _, _, lat, _ in points[:3]]
    lngs = [lng for _, _, _, lng in points[:3]]
    a, b, c = _resoudre_3x3(matrice, lats)
    d, e, f = _resoudre_3x3(matrice, lngs)

    def transform(fx, fy):
        return a * fx + b * fy + c, d * fx + e * fy + f

    centre_lat, centre_lng = transform(0.5, 0.5)
    cos_lat = math.cos(math.radians(centre_lat))

    lat_g, lng_g = transform(0.0, 0.5)
    lat_d, lng_d = transform(1.0, 0.5)
    dx_m = (lng_d - lng_g) * METRES_PAR_DEGRE_LAT * cos_lat
    dy_m = (lat_d - lat_g) * METRES_PAR_DEGRE_LAT
    largeur_m = (dx_m**2 + dy_m**2) ** 0.5
    bearing_x = math.degrees(math.atan2(dx_m, dy_m)) % 360
    rotation_deg = (bearing_x - 90) % 360

    lat_h, lng_h = transform(0.5, 0.0)
    lat_b, lng_b = transform(0.5, 1.0)
    dx_m2 = (lng_b - lng_h) * METRES_PAR_DEGRE_LAT * cos_lat
    dy_m2 = (lat_b - lat_h) * METRES_PAR_DEGRE_LAT
    hauteur_m = (dx_m2**2 + dy_m2**2) ** 0.5

    return {
        "centre_latitude": round(centre_lat, 6),
        "centre_longitude": round(centre_lng, 6),
        "largeur_m": round(largeur_m, 2),
        "hauteur_m": round(hauteur_m, 2),
        "rotation_deg": round(rotation_deg, 2),
    }


def _resoudre_3x3(matrice, vecteur):
    """Resout M*x = v (3 equations, 3 inconnues) par elimination de Gauss avec pivot partiel."""
    m = [row[:] + [vecteur[i]] for i, row in enumerate(matrice)]
    for i in range(3):
        pivot = max(range(i, 3), key=lambda r: abs(m[r][i]))
        m[i], m[pivot] = m[pivot], m[i]
        if abs(m[i][i]) < 1e-12:
            raise ValueError("Points de controle degeneres (colineaires).")
        for r in range(3):
            if r != i:
                facteur = m[r][i] / m[i][i]
                for col in range(i, 4):
                    m[r][col] -= facteur * m[i][col]
    return [m[i][3] / m[i][i] for i in range(3)]
