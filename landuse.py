"""Rainfall frequency factors and exact vector overlay of watershed land uses."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import fiona
from rasterio.crs import CRS
from rasterio.warp import transform_geom
from shapely.geometry import shape
from shapely.ops import unary_union


# Máximas lluvias diarias en la España peninsular, table supplied by the user.
# Columns correspond to T = 2, 5, 10, 25, 50, 100, 200, 500 years.
RETURN_PERIODS = (2, 5, 10, 25, 50, 100, 200, 500)
_YT_ROWS = {
    30: (0.935, 1.194, 1.377, 1.625, 1.823, 2.022, 2.251, 2.541),
    31: (0.932, 1.198, 1.385, 1.640, 1.854, 2.068, 2.296, 2.602),
    32: (0.929, 1.202, 1.400, 1.671, 1.884, 2.098, 2.342, 2.663),
    33: (0.927, 1.209, 1.415, 1.686, 1.915, 2.144, 2.388, 2.724),
    34: (0.924, 1.213, 1.423, 1.717, 1.930, 2.174, 2.434, 2.785),
    35: (0.921, 1.217, 1.438, 1.732, 1.961, 2.220, 2.480, 2.831),
    36: (0.919, 1.225, 1.446, 1.747, 1.991, 2.251, 2.525, 2.892),
    37: (0.917, 1.232, 1.461, 1.778, 2.022, 2.281, 2.571, 2.953),
    38: (0.914, 1.240, 1.469, 1.793, 2.052, 2.327, 2.617, 3.014),
    39: (0.912, 1.243, 1.484, 1.808, 2.083, 2.357, 2.663, 3.067),
    40: (0.909, 1.247, 1.492, 1.839, 2.113, 2.403, 2.708, 3.128),
    41: (0.906, 1.255, 1.507, 1.854, 2.144, 2.434, 2.754, 3.189),
    42: (0.904, 1.259, 1.514, 1.884, 2.174, 2.480, 2.800, 3.250),
    43: (0.901, 1.263, 1.534, 1.900, 2.205, 2.510, 2.846, 3.311),
    44: (0.898, 1.270, 1.541, 1.915, 2.220, 2.556, 2.892, 3.372),
    45: (0.896, 1.274, 1.549, 1.945, 2.251, 2.586, 2.937, 3.433),
    46: (0.894, 1.278, 1.564, 1.961, 2.281, 2.632, 2.983, 3.494),
    47: (0.892, 1.286, 1.579, 1.991, 2.312, 2.663, 3.044, 3.555),
    48: (0.890, 1.289, 1.595, 2.007, 2.342, 2.708, 3.098, 3.616),
    49: (0.887, 1.293, 1.603, 2.022, 2.373, 2.739, 3.128, 3.677),
    50: (0.885, 1.297, 1.610, 2.052, 2.403, 2.785, 3.189, 3.738),
    51: (0.883, 1.301, 1.625, 2.068, 2.434, 2.815, 3.220, 3.799),
    52: (0.881, 1.308, 1.640, 2.098, 2.464, 2.861, 3.281, 3.860),
}


def yt_factors(cv: float) -> dict[int, float]:
    """Linear interpolation in Cv only; never extrapolate beyond the supplied table."""
    value = float(cv)
    if not 0.30 <= value <= 0.52:
        raise ValueError('Cv debe estar entre 0,30 y 0,52 para esta tabla de YT.')
    scaled = value * 100
    low = min(52, max(30, int(scaled + 1e-9)))
    high = min(low + 1, 52)
    fraction = max(0, min(1, scaled - low))
    return {period: round(_YT_ROWS[low][i] * (1-fraction) +
                          _YT_ROWS[high][i] * fraction, 6)
            for i, period in enumerate(RETURN_PERIODS)}


def _label(raw: object) -> str:
    if raw is None or not str(raw).strip():
        return 'Sin clasificar'
    label = str(raw).strip()
    # The supplied layer has a second UTF-8 decoding error on accented labels.
    for _ in range(2):
        if 'Ã' not in label and 'Â' not in label:
            break
        try:
            label = label.encode('latin-1').decode('utf-8')
        except UnicodeError:
            break
    return label.replace('\u00ad', '')


def landuse_summary(basin_file: Path, landuse_file: Path) -> dict:
    """Clip source polygons against the basin, preserving projected vector areas."""
    with fiona.open(basin_file, layer='cuenca') as basins:
        if not basins.crs:
            raise ValueError('La cuenca no tiene sistema de coordenadas.')
        basin_crs = CRS.from_user_input(basins.crs)
        if not basin_crs.is_projected or basin_crs.linear_units != 'metre':
            raise ValueError('La cuenca debe tener coordenadas proyectadas en metros.')
        basin = unary_union([shape(feature['geometry']) for feature in basins])
    if basin.is_empty:
        raise ValueError('La cuenca guardada está vacía.')
    if not basin.is_valid:
        basin = basin.buffer(0)
    if basin.is_empty:
        raise ValueError('La geometría de la cuenca no se ha podido reparar.')
    totals = defaultdict(float)
    n = 0
    with fiona.open(landuse_file) as uses:
        if 'TC_SIOSE_C' not in uses.schema['properties']:
            raise ValueError('El GeoPackage no tiene el campo TC_SIOSE_C.')
        if not uses.crs:
            raise ValueError('Los usos del suelo no tienen sistema de coordenadas.')
        source_crs = CRS.from_user_input(uses.crs)
        bounds = basin.bounds
        if source_crs != basin_crs:
            from rasterio.warp import transform_bounds
            bounds = transform_bounds(basin_crs, source_crs, *bounds, densify_pts=21)
        for feature in uses.filter(bbox=bounds):
            if not feature['geometry']:
                continue
            geometry = dict(feature['geometry'])
            if source_crs != basin_crs:
                geometry = transform_geom(source_crs, basin_crs, geometry)
            polygon = shape(geometry)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if polygon.is_empty or not polygon.intersects(basin):
                continue
            area = polygon.intersection(basin).area
            if area:
                label = _label(feature['properties']['TC_SIOSE_C'])
                code = feature['properties'].get('SIOSE_CODE') or ''
                # Only exact, single-use SIOSE codes separate dry and irrigated crops.
                # Compound codes stay visible for individual review.
                if label == 'Cultivo herbáceo' and code == 'CHLsc':
                    label += ' · secano'
                elif label == 'Cultivo herbáceo' and code == 'CHLrr':
                    label += ' · regadío'
                totals[label] += area
                n += 1
    area = basin.area
    return {'cuenca_m2': area, 'usos_m2': sum(totals.values()),
            'desviacion_m2': sum(totals.values()) - area,
            'poligonos_intersectados': n,
            'superficies': [{'uso': name, 'm2': round(value, 3),
                             'ha': round(value / 10_000, 6)}
                            for name, value in sorted(totals.items())]}


def save_landuse_summary(folder: Path, summary: dict, source: Path) -> Path:
    output = folder/'superficies_usos.json'
    output.write_text(json.dumps({'fuente': str(source), **summary},
                                 indent=2, ensure_ascii=False), encoding='utf-8')
    return output
