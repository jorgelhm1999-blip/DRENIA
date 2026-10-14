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
NORM_USES = {
    '11100': NormUse('Tejido urbano continuo', (1, 1, 1, 1)),
    '11200': NormUse('Tejido urbano discontinuo', (24, 14, 8, 6)),
    '11210': NormUse('Estructura urbana abierta', (24, 14, 8, 6)),
    '12100': NormUse('Industrial y comercial', (6, 4, 3, 3)),
    '12100-granja': NormUse('Granjas agrícolas', (24, 14, 8, 6)),
    '12110': NormUse('Zonas industriales', (12, 7, 5, 4)),
    '12120': NormUse('Equipamiento y servicios', (6, 4, 3, 3)),
    '12200': NormUse('Redes viarias y ferroviarias', (1, 1, 1, 1)),
    '12220': NormUse('Complejos ferroviarios', (12, 7, 5, 4)),
    '12300': NormUse('Zonas portuarias', (1, 1, 1, 1)),
    '12400': NormUse('Aeropuertos', (24, 14, 8, 6)),
    '13100': NormUse('Extracción minera', (16, 9, 6, 5)),
    '13200': NormUse('Escombreras y vertederos', (20, 11, 8, 6)),
    '14100': NormUse('Zonas verdes urbanas', (53, 23, 14, 10)),
    '21100': NormUse('Cereales de secano', (34, 21, 14, 12), '<3', 'R/N'),
    '21210': NormUse('Cultivos herbáceos en regadío', (47, 25, 16, 13), '<3', 'R/N'),
    '22100': NormUse('Viñedos', (75, 34, 19, 14), '<3'),
    '22200': NormUse('Frutales', (95, 42, 22, 15), '<3'),
    '22300': NormUse('Olivares', (75, 34, 19, 14), '<3'),
    '23100-prados': NormUse('Prados y praderas', (120, 55, 22, 14), '<3'),
    '24211': NormUse('Cultivos anuales con prados en secano', (30, 19, 13, 10), '<3', 'R/N'),
    '24221': NormUse('Cultivos anuales con prados en regadío', (47, 25, 16, 13), '<3', 'R/N'),
    '24310': NormUse('Cultivos secano y vegetación natural', (30, 19, 13, 10), '<3', 'R/N'),
    '24320': NormUse('Cultivos regadío y vegetación natural', (47, 25, 16, 13), '<3', 'R/N'),
    '31100': NormUse('Frondosas', (90, 47, 31, 23)),
    '31200': NormUse('Coníferas', (90, 47, 31, 23)),
    '31300': NormUse('Bosque mixto', (90, 47, 31, 23)),
    '32100-pastos': NormUse('Pastizales naturales', (80, 35, 17, 10), '<3'),
    '32300': NormUse('Vegetación esclerófila', (60, 24, 14, 10)),
    '32400': NormUse('Matorral boscoso de transición', (75, 34, 22, 16)),
    '33120': NormUse('Ramblas con poca vegetación', (15, 8, 6, 4)),
    '33200': NormUse('Roquedo', (2, 2, 2, 2)),
    '33300': NormUse('Vegetación escasa', (58, 25, 12, 7), '<3'),
    '41100': NormUse('Humedales y zonas pantanosas', (2, 2, 2, 2)),
    '51100': NormUse('Cursos de agua', (0, 0, 0, 0)),
    '51200': NormUse('Lagos y embalses', (0, 0, 0, 0)),
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
    'Embalse': '51200', 'Lago o laguna': '51200',
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
