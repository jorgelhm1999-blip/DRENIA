"""Reviewable SIOSE-to-5.2-IC table 2.3 equivalences and initial runoff threshold."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormUse:
    label: str
    values: tuple[int, int, int, int]
    slope: str = '—'
    practice: str = '—'


# P0^i in mm. Rows with slope and practice use the user's <3% and R/N assumptions.
# Same Corine code with different land uses is kept as a separate selectable entry.
NORM_USES = {
    '11100': NormUse('Tejido urbano continuo', (1, 1, 1, 1)),
    '11200': NormUse('Tejido urbano discontinuo', (24, 14, 8, 6)),
    '11200-urbanizaciones': NormUse('Urbanizaciones', (24, 14, 8, 6)),
    '11210': NormUse('Estructura urbana abierta', (24, 14, 8, 6)),
    '11220': NormUse('Urbanizaciones exentas y/o ajardinadas', (24, 14, 8, 6)),
    '12100': NormUse('Industrial y comercial', (6, 4, 3, 3)),
    '12100-granja': NormUse('Granjas agrícolas', (24, 14, 8, 6)),
    '12110': NormUse('Zonas industriales', (12, 7, 5, 4)),
    '12120': NormUse('Equipamiento y servicios', (6, 4, 3, 3)),
    '12200': NormUse('Redes viarias y ferroviarias', (1, 1, 1, 1)),
    '12210': NormUse('Autopistas y autovías', (1, 1, 1, 1)),
    '12220': NormUse('Complejos ferroviarios', (12, 7, 5, 4)),
    '12300': NormUse('Zonas portuarias', (1, 1, 1, 1)),
    '12400': NormUse('Aeropuertos', (24, 14, 8, 6)),
    '13100': NormUse('Extracción minera', (16, 9, 6, 5)),
    '13200': NormUse('Escombreras y vertederos', (20, 11, 8, 6)),
    '13300': NormUse('Zonas de construcción', (24, 14, 8, 6)),
    '14100': NormUse('Zonas verdes urbanas', (53, 23, 14, 10)),
    '14200': NormUse('Instalaciones deportivas y recreativas', (79, 32, 18, 13)),
    '14210': NormUse('Campos de golf', (79, 32, 18, 13)),
    '14220': NormUse('Otras instalaciones deportivas', (53, 23, 14, 10)),
    '21100': NormUse('Cereales de secano', (34, 21, 14, 12), '<3', 'R/N'),
    '21100-viveros': NormUse('Viveros de secano', (75, 34, 19, 14), '<3'),
    '21100-hortalizas': NormUse('Hortalizas de secano', (29, 19, 14, 11), '<3', 'R/N'),
    '21100-abandonadas': NormUse('Tierras abandonadas', (20, 14, 11, 8), '<3'),
    '21200': NormUse('Terrenos regados permanentemente', (47, 25, 16, 13), '<3', 'R/N'),
    '21210': NormUse('Cultivos herbáceos en regadío', (47, 25, 16, 13), '<3', 'R/N'),
    '21220': NormUse('Otras zonas de irrigación', (47, 25, 16, 13), '<3', 'R/N'),
    '21300': NormUse('Arrozales', (47, 25, 16, 13)),
    '22100': NormUse('Viñedos', (75, 34, 19, 14), '<3'),
    '22110': NormUse('Viñedos en secano', (75, 34, 19, 14), '<3'),
    '22120': NormUse('Viñedos en regadío', (75, 34, 19, 14), '<3'),
    '22200': NormUse('Frutales', (95, 42, 22, 15), '<3'),
    '22210': NormUse('Frutales en secano', (75, 34, 19, 14), '<3'),
    '22220': NormUse('Frutales en regadío', (95, 42, 22, 15), '<3'),
    '22221': NormUse('Cítricos', (95, 42, 22, 15), '<3'),
    '22222': NormUse('Frutales tropicales', (95, 42, 22, 15), '<3'),
    '22223': NormUse('Otros frutales en regadío', (95, 42, 22, 15), '<3'),
    '22300': NormUse('Olivares', (75, 34, 19, 14), '<3'),
    '22310': NormUse('Olivares en secano', (75, 34, 19, 14), '<3'),
    '22320': NormUse('Olivares en regadío', (75, 34, 19, 14), '<3'),
    '23100-prados': NormUse('Prados y praderas', (120, 55, 22, 14), '<3'),
    '23100-abandonados': NormUse('Pastos en tierras abandonadas', (58, 25, 12, 7), '<3'),
    '23100-arbolados': NormUse('Prados arbolados', (120, 55, 22, 14), '<3'),
    '24110': NormUse('Anuales y permanentes en secano', (66, 29, 15, 10), '<3'),
    '24120': NormUse('Anuales y permanentes en regadío', (106, 48, 22, 15), '<3'),
    '24211': NormUse('Cultivos anuales con prados en secano', (30, 19, 13, 10), '<3', 'R/N'),
    '24212': NormUse('Mosaico permanentes en secano', (75, 34, 19, 14), '<3'),
    '24213': NormUse('Mosaico anuales y permanentes secano', (66, 29, 15, 10), '<3'),
    '24221': NormUse('Cultivos anuales con prados en regadío', (47, 25, 16, 13), '<3', 'R/N'),
    '24222': NormUse('Mosaico permanentes en regadío', (95, 42, 22, 15), '<3'),
    '24223': NormUse('Mosaico anuales y permanentes regadío', (106, 48, 22, 15), '<3'),
    '24230': NormUse('Mosaico mixto secano y regadío', (37, 22, 14, 11), '<3', 'R/N'),
    '24310': NormUse('Cultivos secano y vegetación natural', (30, 19, 13, 10), '<3', 'R/N'),
    '24320': NormUse('Cultivos regadío y vegetación natural', (47, 25, 16, 13), '<3', 'R/N'),
    '24330': NormUse('Prados con vegetación natural', (120, 55, 22, 14), '<3'),
    '24400': NormUse('Sistemas agroforestales', (80, 35, 17, 10), '<3'),
    '24410': NormUse('Pastizales con arbolado adehesado', (80, 35, 17, 10), '<3'),
    '24420': NormUse('Cultivos con arbolado adehesado', (80, 35, 17, 10), '<3'),
    '31100': NormUse('Frondosas', (90, 47, 31, 23)),
    '31110': NormUse('Frondosas perennifolias', (90, 47, 31, 23)),
    '31120': NormUse('Frondosas caducifolias', (90, 47, 31, 23)),
    '31130': NormUse('Otras frondosas de plantación', (94, 42, 22, 15), '<3'),
    '31140': NormUse('Mezclas de frondosas', (90, 47, 31, 23)),
    '31150': NormUse('Bosques de ribera', (76, 34, 22, 16)),
    '31160': NormUse('Laurisilva macaronésica', (90, 47, 31, 23)),
    '31200': NormUse('Coníferas', (90, 47, 31, 23)),
    '31210': NormUse('Coníferas de hojas aciculares', (90, 47, 31, 23)),
    '31220': NormUse('Coníferas de hojas cupresáceas', (90, 47, 31, 23)),
    '31300': NormUse('Bosque mixto', (90, 47, 31, 23)),
    '32100-pastos': NormUse('Pastizales naturales', (80, 35, 17, 10), '<3'),
    '32100-alpinos': NormUse('Prados alpinos', (120, 55, 22, 14), '<3'),
    '32100-aluviales': NormUse('Herbáceas de llanuras aluviales', (120, 55, 22, 14), '<3'),
    '32110': NormUse('Pastizales supraforestales', (120, 55, 22, 14), '<3'),
    '32111': NormUse('Pastizales supraforestales oceánicos', (120, 55, 22, 14), '<3'),
    '32112': NormUse('Pastizales supraforestales mediterráneos', (57, 25, 12, 7), '<3'),
    '32121': NormUse('Otros pastizales templado oceánicos', (79, 35, 17, 10), '<3'),
    '32122': NormUse('Otros pastizales mediterráneos', (57, 25, 12, 7), '<3'),
    '32200': NormUse('Landas y matorrales mesófilos', (76, 34, 22, 16)),
    '32210': NormUse('Matorral de clima húmedo', (76, 34, 22, 16)),
    '32220': NormUse('Fayal-brezal macaronésico', (60, 24, 14, 10)),
    '32300': NormUse('Vegetación esclerófila', (60, 24, 14, 10)),
    '32311': NormUse('Matorral denso', (75, 34, 22, 16)),
    '32312': NormUse('Matorral muy poco denso', (60, 24, 14, 10)),
    '32320': NormUse('Matorral xerófilo macaronésico', (40, 17, 8, 5)),
    '32400': NormUse('Matorral boscoso de transición', (75, 34, 22, 16)),
    '32400-claras': NormUse('Claras de bosques', (40, 17, 8, 5)),
    '32400-empantanadas': NormUse('Zonas empantanadas', (60, 24, 14, 10)),
    '32410': NormUse('Matorral boscoso de frondosas', (75, 34, 22, 16)),
    '32420': NormUse('Matorral boscoso de coníferas', (75, 34, 22, 16)),
    '32430': NormUse('Matorral boscoso mixto', (75, 34, 22, 16)),
    '33110': NormUse('Playas y dunas', (152, 152, 152, 152)),
    '33120': NormUse('Ramblas con poca vegetación', (15, 8, 6, 4)),
    '33200': NormUse('Roquedo', (2, 2, 2, 2)),
    '33210': NormUse('Rocas desnudas de fuerte pendiente', (2, 2, 2, 2)),
    '33220': NormUse('Afloramientos rocosos', (4, 4, 4, 4), '<3'),
    '33230': NormUse('Coladas lávicas cuaternarias', (5, 5, 5, 5), '<3'),
    '33300': NormUse('Vegetación escasa', (58, 25, 12, 7), '<3'),
    '33310': NormUse('Xeroestepa subdesértica', (58, 25, 12, 7), '<3'),
    '33320': NormUse('Cárcavas y erosión', (15, 8, 6, 4)),
    '33330': NormUse('Vegetación escasa orófila', (58, 25, 12, 7), '<3'),
    '33400': NormUse('Zonas quemadas', (15, 8, 6, 4)),
    '33500': NormUse('Glaciares y nieve', (0, 0, 0, 0)),
    '41100': NormUse('Humedales y zonas pantanosas', (2, 2, 2, 2)),
    '41200': NormUse('Turberas y prados turbosos', (248, 99, 25, 16)),
    '42100': NormUse('Marismas', (2, 2, 2, 2)),
    '42200': NormUse('Salinas', (5, 5, 5, 5)),
    '42300': NormUse('Zonas llanas intermareales', (0, 0, 0, 0)),
    '51100': NormUse('Cursos de agua', (0, 0, 0, 0)),
    '51110': NormUse('Ríos y cauces naturales', (0, 0, 0, 0)),
    '51120': NormUse('Canales artificiales', (0, 0, 0, 0)),
    '51210': NormUse('Lagos y lagunas', (0, 0, 0, 0)),
    '51220': NormUse('Embalses', (0, 0, 0, 0)),
    '52100': NormUse('Lagunas costeras', (0, 0, 0, 0)),
    '52200': NormUse('Estuarios', (0, 0, 0, 0)),
    '52300': NormUse('Mares y océanos', (0, 0, 0, 0)),
}

# None is intentional: the SIOSE class spans multiple different normative rows.
DEFAULT_EQUIVALENCES = {
    'Casco': '11100', 'Ensanche': '11210', 'Discontinuo': '11200',
    'Industrial': '12110', 'Servicio dotacional': '12120',
    'Red viaria o ferroviaria': None, 'Zona verde urbana': '14100',
    'Instalación agrícola y/o ganadera': '12100-granja',
    'Extracción minera': '13100', 'Infraestructura de residuos': '13200',
    'Infraestructura de suministro': None, 'Aeropuerto': '12400',
    'Puerto': '12300', 'Cultivo herbáceo': None,
    'Cultivo herbáceo · secano': '21100',
    'Cultivo herbáceo · regadío': '21210',
    'Asentamiento agrícola y huerta': None, 'Invernadero': None,
    'Viñedo': '22100', 'Frutal no cítrico': '22200',
    'Olivar': '22300', 'Otros cultivos leñosos': None,
    'Prado': '23100-prados', 'Pastizal o herbazal': None,
    'Combinación de cultivos': None, 'Combinación de cultivos leñosos': None,
    'Combinación de cultivos con vegetación': None,
    'Bosque de frondosas': '31100', 'Bosque de coníferas': '31200',
    'Bosque mixto': '31300', 'Instalación forestal': None,
    'Matorral': None, 'Combinación de vegetación': None,
    'Suelo desnudo': None, 'Roquedo': '33200',
    'Curso de agua': '51100', 'Lámina de agua artificial': '51200',
    'Embalse': '51220', 'Lago o laguna': '51210',
    'Zona húmeda y pantanosa': '41100',
}

GROUPS = ('A', 'B', 'C', 'D')


def threshold_summary(areas: dict, group: str, equivalences: dict) -> dict:
    if group not in GROUPS:
        raise ValueError('El grupo de suelo debe ser A, B, C o D.')
    rows = []
    covered = 0.0
    weighted = 0.0
    total = 0.0
    for label, area in sorted(areas.items()):
        if area <= 0:
            continue
        code = equivalences.get(label)
        if code is not None and code not in NORM_USES:
            raise ValueError(f'Fila normativa desconocida: {code}.')
        initial = NORM_USES[code].values[GROUPS.index(group)] if code else None
        total += area
        if initial is not None:
            covered += area
            weighted += area * initial
        rows.append({'uso_siose': label, 'area_m2': area, 'fila_52ic': code,
                     'p0_inicial_mm': initial})
    return {'grupo_suelo': group, 'pendiente_supuesta': '<3 %',
            'practica_cultivo_supuesta': 'R/N donde procede',
            'area_clasificada_m2': covered, 'area_total_m2': total,
            'area_sin_equivalencia_m2': total-covered,
            'p0_inicial_ponderado_mm': weighted/total if total and covered == total else None,
            'filas': rows}
