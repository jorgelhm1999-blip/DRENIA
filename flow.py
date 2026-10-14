"""Traceable rational-method calculation following 5.2-IC and the example workbook."""
from __future__ import annotations

import math

from landuse import RETURN_PERIODS, yt_factors


def concentration_time(length_km: float, slope: float) -> float:
    if length_km <= 0 or slope <= 0:
        raise ValueError('Longitud y pendiente del cauce deben ser positivas.')
    return 0.3 * (length_km / slope**0.25)**0.76


def rational_flows(*, area_km2: float, p0_initial: float, cv: float,
                   mean_daily_rain_mm: float, beta_m: float, torrentiality: float,
                   tc_hours: float, ft: dict[int, float]) -> dict:
    if min(area_km2, mean_daily_rain_mm, beta_m, torrentiality, tc_hours) <= 0:
        raise ValueError('Área, precipitación, βm, I₁/Id y Tc deben ser positivos.')
    if area_km2 >= 50:
        raise ValueError('Esta modalidad del método racional se limita a cuencas menores de 50 km².')
    if p0_initial < 0:
        raise ValueError('El umbral inicial no puede ser negativo.')
    factors = yt_factors(cv)
    ka = 1 if area_km2 < 1 else 1 - math.log10(area_km2)/15
    kt = 1 + tc_hours**1.25/(tc_hours**1.25+14)
    exponent = 3.5287 - 2.5287*tc_hours**0.1
    rows = []
    for t in RETURN_PERIODS:
        factor = ft.get(t)
        if factor is None or factor <= 0:
            rows.append({'periodo': t, 'estado': 'Falta Ft'})
            continue
        pd = mean_daily_rain_mm*factors[t]
        p0 = p0_initial*beta_m*factor
        effective_pd = pd*ka
        if p0 == 0:
            runoff = 1.0  # impervious catchment / water surface
        elif effective_pd <= p0:
            runoff = 0.0
        else:
            ratio = effective_pd/p0
            runoff = (ratio-1)*(ratio+23)/(ratio+11)**2
        intensity = effective_pd/24 * torrentiality**exponent
        q = runoff*intensity*area_km2*kt/3.6
        rows.append({'periodo': t, 'yt': factors[t], 'pd_mm': pd,
                     'ft': factor, 'beta': beta_m*factor, 'p0_mm': p0,
                     'intensidad_mm_h': intensity, 'coeficiente_escorrentia': runoff,
                     'caudal_m3_s': q, 'estado': 'Calculado'})
    return {'area_km2': area_km2, 'p0_inicial_mm': p0_initial,
            'cv': cv, 'precipitacion_media_diaria_mm': mean_daily_rain_mm,
            'beta_m': beta_m, 'i1_id': torrentiality,
            'tc_h': tc_hours, 'ka': ka, 'kt': kt, 'periodos': rows}
