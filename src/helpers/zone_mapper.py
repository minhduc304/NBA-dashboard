"""Zone Mapper - Pure functions for mapping shot coordinates to zones."""

# Standard zone names used throughout the application
ZONE_NAMES = [
    'Restricted Area',
    'Paint (Non-RA)',
    'Mid-Range',
    'Left Corner 3',
    'Right Corner 3',
    'Above the Break 3',
]

# Zone coordinate boundaries (approximate)
# Coordinates are in 10ths of feet from basket center
ZONE_BOUNDARIES = {
    'Restricted Area': {'radius': 40},
    'Paint (Non-RA)': {'x': (-80, 80), 'y': (-50, 140)},
    'Mid-Range': {'x': (-220, 220), 'y': (-50, 140)},
    'Left Corner 3': {'x': (-250, -220), 'y': (-50, 90)},
    'Right Corner 3': {'x': (220, 250), 'y': (-50, 90)},
    'Above the Break 3': {'x': (-250, 250), 'y': (90, 470)},
}

# 3-point line distance (in 10ths of feet)
THREE_POINT_DISTANCE = 237.5
CORNER_THREE_DISTANCE = 220


def get_zone_from_coordinates(x: int, y: int) -> str:
    """
    Map shot coordinates to zone name.

    This is a PURE FUNCTION - easy to test with known coordinates.

    Args:
        x: X coordinate (negative = left, positive = right)
        y: Y coordinate (distance from baseline)

    Returns:
        Zone name string
    """
    # Distance from basket
    distance = (x**2 + y**2) ** 0.5

    # Check corner 3s first (corners have shorter 3pt distance)
    if abs(x) >= 220 and y < 90:
        return 'Left Corner 3' if x < 0 else 'Right Corner 3'

    # Check if beyond 3-point arc
    if distance > THREE_POINT_DISTANCE:
        return 'Above the Break 3'

    # Check restricted area (within 4 feet of basket)
    if distance <= 40:
        return 'Restricted Area'

    # Check paint (non-restricted area)
    if abs(x) <= 80 and y <= 140:
        return 'Paint (Non-RA)'

    # Everything else is mid-range
    return 'Mid-Range'


def normalize_zone_name(raw_name: str) -> str:
    """
    Standardize zone names from different sources.

    This is a PURE FUNCTION that maps various API naming conventions
    to our standard zone names.

    Args:
        raw_name: Raw zone name from API

    Returns:
        Standardized zone name
    """
    mappings = {
        # NBA API variants
        'restricted area': 'Restricted Area',
        'in the paint (non-ra)': 'Paint (Non-RA)',
        'in the paint': 'Paint (Non-RA)',
        'paint': 'Paint (Non-RA)',
        'mid-range': 'Mid-Range',
        'midrange': 'Mid-Range',
        'mid range': 'Mid-Range',
        'left corner 3': 'Left Corner 3',
        'left corner': 'Left Corner 3',
        'right corner 3': 'Right Corner 3',
        'right corner': 'Right Corner 3',
        'above the break 3': 'Above the Break 3',
        'above break 3': 'Above the Break 3',
        'arc 3': 'Above the Break 3',
        'backcourt': 'Above the Break 3',
    }

    normalized = mappings.get(raw_name.lower().strip())
    if normalized:
        return normalized

    # If not found, return original (capitalized)
    return raw_name.title()


def get_zone_value(zone_name: str) -> float:
    """
    Get expected point value for a zone.

    Args:
        zone_name: Standardized zone name

    Returns:
        Expected points per shot (considering 2 vs 3 pointers)
    """
    # These are rough expected values based on league averages
    zone_values = {
        'Restricted Area': 1.30,  # ~65% FG% * 2 points
        'Paint (Non-RA)': 0.82,   # ~41% FG% * 2 points
        'Mid-Range': 0.80,        # ~40% FG% * 2 points
        'Left Corner 3': 1.17,    # ~39% FG% * 3 points
        'Right Corner 3': 1.17,   # ~39% FG% * 3 points
        'Above the Break 3': 1.08, # ~36% FG% * 3 points
    }

    return zone_values.get(zone_name, 1.0)


def is_three_pointer(zone_name: str) -> bool:
    """Check if zone is a 3-point zone."""
    return '3' in zone_name


def is_paint(zone_name: str) -> bool:
    """Check if zone is in the paint (restricted area or non-RA paint)."""
    return zone_name in ['Restricted Area', 'Paint (Non-RA)']
