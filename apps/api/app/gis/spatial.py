import json
import math
from typing import Dict, Any, Tuple, Union
import shapely
from shapely.geometry import shape, mapping, Point, Polygon, MultiPolygon, LineString
from shapely.ops import transform

# Pure python equirectangular metric projection around center latitude (e.g. 28.0)
def create_metric_projectors(center_lat: float = 28.0):
    rad = math.radians(center_lat)
    cos_lat = math.cos(rad)
    m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * rad) + 1.175 * math.cos(4 * rad)
    m_per_deg_lon = 111412.84 * cos_lat - 93.5 * math.cos(3 * rad)

    def to_metric(x, y, z=None):
        return x * m_per_deg_lon, y * m_per_deg_lat

    def to_wgs84(x, y, z=None):
        return x / m_per_deg_lon, y / m_per_deg_lat

    return to_metric, to_wgs84

_to_metric, _to_wgs84 = create_metric_projectors(28.0)

def to_shapely(geom_data: Union[str, Dict[str, Any]]) -> shapely.Geometry:
    """Parse a GeoJSON dict or string into a valid Shapely geometry."""
    if isinstance(geom_data, str):
        geom_dict = json.loads(geom_data)
    else:
        geom_dict = geom_data
    geom = shape(geom_dict)
    if not geom.is_valid:
        geom = shapely.validation.make_valid(geom)
    return geom

def to_geojson(geom: shapely.Geometry) -> Dict[str, Any]:
    """Convert a Shapely geometry into a GeoJSON mapping."""
    if not geom.is_valid:
        geom = shapely.validation.make_valid(geom)
    return mapping(geom)

def to_geojson_str(geom: shapely.Geometry) -> str:
    """Convert a Shapely geometry into a JSON string."""
    return json.dumps(to_geojson(geom))

def project_to_metric(geom: shapely.Geometry) -> shapely.Geometry:
    """Transform geometry from EPSG:4326 to Projected Metric coordinates for accurate planar ops."""
    return transform(_to_metric, geom)

def project_to_wgs84(geom: shapely.Geometry) -> shapely.Geometry:
    """Transform geometry from Projected Metric coordinates back to EPSG:4326."""
    return transform(_to_wgs84, geom)

def buffer_meters(geom: shapely.Geometry, distance_meters: float) -> shapely.Geometry:
    """Accurately buffer a WGS84 geometry in meters using projected metric coordinates."""
    metric_geom = project_to_metric(geom)
    buffered_metric = metric_geom.buffer(distance_meters)
    buffered_wgs84 = project_to_wgs84(buffered_metric)
    if not buffered_wgs84.is_valid:
        buffered_wgs84 = shapely.validation.make_valid(buffered_wgs84)
    return buffered_wgs84

def calculate_distance_meters(geom1: shapely.Geometry, geom2: shapely.Geometry) -> float:
    """Compute distance in meters between two WGS84 geometries."""
    m1 = project_to_metric(geom1)
    m2 = project_to_metric(geom2)
    return float(m1.distance(m2))

def intersects(geom1: shapely.Geometry, geom2: shapely.Geometry) -> bool:
    """Check if two geometries intersect."""
    return geom1.intersects(geom2)
