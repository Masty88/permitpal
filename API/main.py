"""
Created on Tue Feb  4 10:12:31 2025

@author: mikel
"""
from fastapi import FastAPI, File, UploadFile, HTTPException
import shutil
import ifcopenshell
import ifcopenshell.geom
import json
import os
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import MultiPoint, Polygon
from pyproj import Transformer
from fastapi.middleware.cors import CORSMiddleware
import os
import importlib
from speckle_transform import IFCToSpeckle
from speckle_object import send_to_speckle
import math
import shapely
from process_geometry.run_all import main

# directory to save uploaded files
UPLOAD_FOLDER = "uploads"
# Step 1: Define project variables
SPECKLE_SERVER = "https://app.speckle.systems/"
SPECKLE_TOKEN = "e7a3b0340b976840e6c6c246b94f8cb83f4fc863df"  # Replace with your token
STREAM_ID = "ac4a00b20e"  # Replace with your stream ID
DATA_ID = "5308d7379d"  # Replace with your data ID
BRANCH_NAME = "main"  # Or whatever branch you want to use
BRANCH_DATA="emmanuelle"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = FastAPI()

origins = [
    "http://localhost:4321",  # Allow requests from your Astro client
    "http://localhost",       # Allow requests from localhost
    "http://127.0.0.1:4321",  # Allow requests from 127.0.0.1
    "*", # allow all origins
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)


"""ifcopenshell functions"""

def get_building_height(model):
    """
    To get simple height from OverallHeight
    """
    heights = []
    for building in model.by_type("IfcBuilding"):
        if hasattr(building, "OverallHeight"):
            heights.append(building.OverallHeight)
    return max(heights) if heights else None


def get_building_height_complex(model):
    """
    To get height from either OverallHeight or estimate it from the storey elevations
    """
    heights = []
    floors = model.by_type("IfcBuildingStorey")

    #first try to gert the height of the IfcBuilding
    for building in model.by_type("IfcBuilding"):
        if hasattr(building, "OverallHeight"):
            heights.append(building.OverallHeight)

    #If no OverallHeight, estimate based on storey elevations
    if not heights:
        storey_heights = [
            storey.Elevation for storey in floors if hasattr(storey, "Elevation")
        ]
        if storey_heights:
            estimated_height = max(storey_heights)
        else:
            estimated_height = "Unknown height"
    else:
        estimated_height = max(heights)

    return estimated_height, len(floors)

def get_floor_area_simple(model):
    """
    Use get_floor_area_first_test if your file structure is simple and uses properties directly on elements
    (like GrossFloorArea or NetArea on storeys, slabs, or spaces)
    """
    total_area = 0

    # Try getting the area from IfcBuildingStorey (preferred)
    for storey in model.by_type("IfcBuildingStorey"):
        if hasattr(storey, "GrossFloorArea") and storey.GrossFloorArea is not None:
            total_area += storey.GrossFloorArea

    # If no GrossFloorArea, sum up areas from IfcSlab
    if total_area == 0:
        for slab in model.by_type("IfcSlab"):
            for relDefinesByProperties in slab.IsDefinedBy:
                if relDefinesByProperties.is_a("IfcRelDefinesByProperties"):
                    propSet = relDefinesByProperties.RelatingPropertyDefinition
                    if propSet.is_a("IfcPropertySet"):
                        for prop in propSet.HasProperties:
                            if prop.Name == "NetArea": # Some models use NetArea
                                total_area += prop.NominalValue.wrappedValue

    # If still no area, try summing up IfcSpace areas
    if total_area == 0:
        for space in model.by_type("IfcSpace"):
            for relDefinesByProperties in space.IsDefinedBy:
                if relDefinesByProperties.is_a("IfcRelDefinesByProperties"):
                    propSet = relDefinesByProperties.RelatingPropertyDefinition
                    if propSet.is_a("IfcpropertySet"):
                        for prop in propSet.HasProperties:
                            if prop.Name == "GrossFloorArea":
                                total_area += prop.NominalValue.wrappedValue

    return total_area if total_area > 0 else "Unknown area"


def save_to_json(data, file_path):
    """
    Save data to a JSON file, ensuring all values are JSON serializable.
    """
    def ensure_serializable(obj):
        """ Recursively convert all values to JSON-friendly Python types """
        if isinstance(obj, (int, float, str, bool, type(None))):
            return obj  # Already JSON serializable
        elif isinstance(obj, dict):
            return {key: ensure_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [ensure_serializable(item) for item in obj]
        elif hasattr(obj, "tolist"):  # Handle lists/arrays from other libraries
            return obj.tolist()
        return str(obj)  # Convert unknown objects to strings

    # Convert data before saving
    serializable_data = ensure_serializable(data)

    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(serializable_data, json_file, indent=4)

    #print(f"Data saved to {file_path}")

def get_floor_area(model):
    """Use get_floor_area for more complex files where area might be stored in related properties or element quantities,
    and if you want more flexibility in handling different ways area data can be structured
    """
    total_area = 0

    # Try getting area from IfcBuildingStorey
    for storey in model.by_type("IfcBuildingStorey"):
        for relDefinesByProperties in storey.IsDefinedBy:

            if relDefinesByProperties.is_a("IfcRelDefinesByProperties"):
                propSet = relDefinesByProperties.RelatingPropertyDefinition

                # If area is in IfcPropertySet
                if propSet.is_a("IfcPropertySet"):
                    for prop in propSet.HasProperties:
                        if prop.Name in ["Max Full Floors", "NetFloorArea"]:  # Update based on debug output
                            total_area += prop.NominalValue.wrappedValue

                # If area is in IfcElementQuantity
                elif propSet.is_a("IfcElementQuantity"):
                    for quantity in propSet.Quantities:
                        if quantity.is_a("IfcQuantityArea"):
                            total_area += quantity.AreaValue

    return total_area if total_area > 0 else "Unknown area"

"""Functions based on Geopandas"""

def generate_building_coords(center_x, center_y, width=12, length=24):
    """
    Generate building coordinates for a rectangular building centered at (center_x, center_y).
    """
    half_width = width / 2
    half_length = length / 2

    return [
        (center_x + half_width, center_y + half_length),
        (center_x - half_width, center_y + half_length),
        (center_x - half_width, center_y - half_length),
        (center_x + half_width, center_y - half_length)
    ]

def check_zoning(building_polygon, zoning_map):
    """
    Check if a building is within any zoning area.
    """
    within_zoning = zoning_map.contains(building_polygon)
    return zoning_map[within_zoning]


def check_plot(building_polygon, plot_map):
    """
    Check which plots intersect with a given building polygon.
    """

    intersecting_plots = plot_map[plot_map.intersects(building_polygon)]
    return intersecting_plots

import matplotlib.pyplot as plt
from shapely.geometry import Point

def plot_building_and_zoning(building_polygon, zoning_map, lv95_coords, vertices, zoom_factor=1):
    """
    Plot the zoning map, the building polygon, and an additional polygon from vertices.
    Also zooms into the area of both polygons and adds a red point at the building's center.

    :param building_polygon: The building polygon to plot.
    :param zoning_map: The zoning map to plot as the background.
    :param lv95_coords: Coordinates to add a red point (typically the centroid or center of the building).
    :param vertices: A list of vertices for an additional polygon to plot.
    :param zoom_factor: Factor by which to zoom in on the building and vertices (default 1 means no zoom).
    """
    fig, ax = plt.subplots(figsize=(10, 10))
    zoning_map.plot(ax=ax, color='lightgray', edgecolor='black')

    # Plot the red point at the lv95_coords (center of the building)
    ax.plot(lv95_coords[0], lv95_coords[1], 'ro', markersize=8, label="Building Center")

    # Create the building polygon and plot it (if provided)
    if building_polygon:
        x_building, y_building = building_polygon.exterior.xy
        ax.fill(x_building, y_building, color='red', alpha=0.5, label="Building Polygon")



    # Calculate the bounding box of both the building polygon and the additional polygon
    minx_building, miny_building, maxx_building, maxy_building = building_polygon.bounds
    if vertices:
        # Get the bounding box of the additional polygon
        poly = Polygon(vertices)
        minx_vertices, miny_vertices, maxx_vertices, maxy_vertices = poly.bounds
    else:
        minx_vertices, miny_vertices, maxx_vertices, maxy_vertices = minx_building, miny_building, maxx_building, maxy_building

    # Combine the bounding boxes of both the building and additional polygon
    minx = min(minx_building, minx_vertices)
    miny = min(miny_building, miny_vertices)
    maxx = max(maxx_building, maxx_vertices)
    maxy = max(maxy_building, maxy_vertices)

    # Apply zoom based on the combined bounding box of both polygons
    x_margin = (maxx - minx) * zoom_factor
    y_margin = (maxy - miny) * zoom_factor

    # Set the limits of the plot to zoom into both the building and additional polygon
    ax.set_xlim(minx - x_margin, maxx + x_margin)
    ax.set_ylim(miny - y_margin, maxy + y_margin)

    plt.legend()
    plt.show()


def extract_zoning_restrictions(zoning_with_building):
    """
    Extract zoning restrictions for the building and store them in a dictionary.
    """
    zoning_restrictions = {}

    if not zoning_with_building.empty:
        zoning_restrictions = {
            "Max Building Height": zoning_with_building.get('GEBAEUDEHO', -99).values[0],
            "Total Allowed Height": zoning_with_building.get('GESAMTHOEH', -99).values[0],
            "Max Full Floors": zoning_with_building.get('VOLLGESCHO', 0).values[0],
            "Allowed Attic Floors": zoning_with_building.get('DACHGESCHO', 0).values[0],
            "Floor Area Ratio (FAR)": zoning_with_building.get('AUSNUETZUN', -99).values[0]
        }
    else:
        print("🚨 Building is not within any zoning area!")

    return zoning_restrictions


"""Here is for compdealing with coordinates"""

def dms_to_decimal(degrees, minutes, seconds, microseconds=0):
    """
    Convert Degrees, Minutes, Seconds (DMS) with microseconds to Decimal Degrees.
    """
    # Convert microseconds to milliseconds first
    milliseconds = microseconds / 1000  # Convert microseconds to milliseconds

    # Now convert DMS to decimal degrees
    decimal_value = degrees + (minutes / 60) + ((seconds + (milliseconds / 1000)) / 3600)

    #print(f"DMS to Decimal: {degrees}° {minutes}' {seconds}\" {microseconds}µs → {decimal_value}")  # Debug print
    return decimal_value

def get_ifc_site_coordinates(model):
    """Extracts geolocation from IfcSite (including Eastings/Northings)."""
    for site in model.by_type("IfcSite"):
        latitude = getattr(site, "RefLatitude", None)
        longitude = getattr(site, "RefLongitude", None)
        elevation = getattr(site, "RefElevation", None)

        placement = getattr(site, "ObjectPlacement", None)
        if placement:
            local_placement = placement.RelativePlacement.Location.Coordinates
            easting, northing = local_placement[0], local_placement[1]
        else:
            easting, northing = None, None

        return {
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
            "easting": easting,
            "northing": northing
        }
    return None  # No IfcSite found.

def get_world_coordinates(model):
    """Extracts WGS84 latitude and longitude from IfcSite."""
    for site in model.by_type("IfcSite"):
        if hasattr(site, "RefLatitude") and hasattr(site, "RefLongitude"):
            #print(f"Extracted DMS from IFC: {site.RefLatitude}, {site.RefLongitude}")  # Debug
            return site.RefLatitude, site.RefLongitude
    return None  # No georeferencing found

def wgs84_to_lv95(latitude, longitude):
    """Convert WGS84 (EPSG:4326) to Swiss LV95 (EPSG:2056)."""
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:2056", always_xy=True)
    easting, northing = transformer.transform(longitude, latitude)
    #print(f"WGS84 to LV95: {latitude}, {longitude} → {easting}, {northing}")  # Debug
    return easting, northing

"""Here is for comparing"""

def check_Max_Building_Height():
    return None

""" Here is for getting IFC floor coordinates"""

def get_floor_vertices(model):
    """
    Extract vertices of floor areas (e.g., from IfcSlab or IfcSpace).
    """
    settings = ifcopenshell.geom.settings()
    vertices = []

    # Loop through all IfcSlab objects to get the geometry
    for slab in model.by_type("IfcSlab"):
        shape = ifcopenshell.geom.create_shape(settings, slab)
        if shape:
            geometry = shape.geometry.verts  # Extract vertex list
            for i in range(0, len(geometry), 3):  # Extract (x, y, z) triplets
                vertices.append((geometry[i], geometry[i + 1], geometry[i + 2]))

    # Loop through IfcSpace objects (if no slabs found)
    if not vertices:
        for space in model.by_type("IfcSpace"):
            shape = ifcopenshell.geom.create_shape(settings, space)
            if shape:
                geometry = shape.geometry.verts  # Extract vertex list
                for i in range(0, len(geometry), 3):  # Extract (x, y, z) triplets
                    vertices.append((geometry[i], geometry[i + 1], geometry[i + 2]))

    return vertices


def get_boundary_polygon(vertices):
    """
    Project the 3D points onto a 2D plane (X, Y) and compute the boundary polygon.
    """
    # Project to 2D by removing Z values
    points_2d = [(x, y) for x, y, _ in vertices]

    # Compute the convex hull (outer boundary)
    multipoint = MultiPoint(points_2d)
    boundary_polygon = multipoint.convex_hull  # This creates a polygon

    return boundary_polygon

def get_boundary_polygon_lv95(vertices, lv95_coords):
    """
    Move the vertices by adding LV95 coordinates to their x and y values.
    Project the 3D points onto a 2D plane (X, Y) and compute the boundary polygon.

    :param vertices: List of tuples with (x, y, z) coordinates.
    :param lv95_coords: Tuple of LV95 coordinates (lv95_x, lv95_y).
    :return: A polygon representing the boundary.
    """
    # Shift the x and y values of each vertex by the LV95 coordinates
    shifted_points = [(x + lv95_coords[0], y + lv95_coords[1]) for x, y, _ in vertices]

    # Compute the convex hull (outer boundary)
    multipoint = MultiPoint(shifted_points)
    boundary_polygon = multipoint.convex_hull  # This creates the polygon

    return boundary_polygon


def get_centroid(polygon):
    """
    Compute the centroid of the polygon.
    """
    return polygon.centroid  # Shapely provides centroid directly

def move_vertices(vertices, x_translation, y_translation):
    """
    Move each vertex by a given translation vector (x_translation, y_translation).

    :param vertices: List of vertices in the format [(x, y, z), (x2, y2, z2), ...]
    :param x_translation: The amount to move in the x-direction.
    :param y_translation: The amount to move in the y-direction.
    :return: List of translated vertices.
    """
    # Apply the translation vector to each vertex
    translated_vertices = [(x + x_translation, y + y_translation, z) for x, y, z in vertices]

    return translated_vertices

"""Here is for testing"""


""" Implementing functions to simplify """

def get_absolute_coordinates(placement):
    """Recursively calculates absolute Easting/Northing from IFC placements."""
    if not placement or not hasattr(placement, "RelativePlacement"):
        return [0, 0, 0]  # Default if no placement exists

    # Get Local Placement Coordinates
    location = placement.RelativePlacement.Location.Coordinates if hasattr(placement.RelativePlacement, "Location") else [0, 0, 0]

    # Check if PlacementRelTo exists (meaning it's nested)
    parent_placement = getattr(placement, "PlacementRelTo", None)

    if parent_placement:
        parent_coords = get_absolute_coordinates(parent_placement)
        return [location[i] + parent_coords[i] for i in range(3)]

    return location  # If no parent, return local coordinates

def extract_site_coordinates(model):

    for site in model.by_type("IfcMapConversion"):
        easting = getattr(site, "Eastings", None)  # Ensure it exists
        northing = getattr(site, "Northings", None)  # Ensure it exists)

    return (easting,northing)

def extract_site_rotation(model):

    for site in model.by_type("IfcGeometricRepresentationContext"):
        rotation = getattr(site, "TrueNorth", None)  # Ensure it exists
    print("this is the rotation")
    print(rotation)


    return (rotation)

def get_lv95_coords(path):
    """
    """
    model = ifcopenshell.open(path)
    #print("test coords")
    #print(get_ifc_site_coordinates(model))
    world_coords = get_world_coordinates(model)



    if world_coords:
        lat_dms, lon_dms = world_coords  # Unpack tuple of tuples

        # Convert DMS to Decimal
        latitude = dms_to_decimal(*lat_dms)
        longitude = dms_to_decimal(*lon_dms)

        #print(f"Converted WGS84: Lat = {latitude}, Lon = {longitude}")

        # Convert to Swiss LV95
        lv95_coords = wgs84_to_lv95(latitude, longitude)
        #print(f"Swiss LV95 Coordinates: {lv95_coords}")  # (Easting, Northing)
    else:
        print("No georeferencing data found in the IFC model.")
        # Get floor vertices

    return lv95_coords


def get_north_rotation(north_vector):
    """
    Returns a function to rotate points so that the given north_vector aligns with (0,1).

    Args:
        north_vector (tuple): A tuple (north_x, north_y) representing the IfcDirection.

    Returns:
        function: A function that rotates (x, y) coordinates accordingly.
    """
    return math.atan(north_vector[1]/north_vector[0])


def get_Building_data(path, zoning_map_path, result_from_ata, plot_map_path):
    """
    Function to extract building data and zoning information, including restrictions.
    """

    model = ifcopenshell.open(path)
    zoning_map = gpd.read_file(zoning_map_path)
    plot_map = gpd.read_file(plot_map_path)


    lv95_coords = extract_site_coordinates(model)
    rotation = extract_site_rotation(model)
    print(type(rotation))
    rotation_XY= (rotation[0][0],rotation[0][1])
    print(rotation_XY)
    angle = math.degrees(get_north_rotation(rotation_XY))+90
    angle = -angle
    vertices = get_floor_vertices(model)

    boundary_polygon = get_boundary_polygon(vertices)
    vertices_95 = move_vertices(vertices, lv95_coords[0], lv95_coords[1])
    boundary_polygon_lv95 = get_boundary_polygon(vertices_95)
    boundary_95_rotated = shapely.affinity.rotate(boundary_polygon_lv95,angle,lv95_coords)
    vertices_95_rotated = shapely.affinity.rotate(shapely.MultiPoint(vertices_95),angle,lv95_coords)
    centroid_lv95 = get_centroid(boundary_95_rotated)
    print("centroid")
    print(centroid_lv95)

    #We are going to use the centroid of the polygonal projection of the slabs to get the position of the building.
    #centroid_lv95 = [centroid.x + lv95_coords[0], centroid.y + lv95_coords[1]]


    #Generate building coordinates
    center_x, center_y = centroid_lv95.x, centroid_lv95.y
    building_coords = generate_building_coords(center_x, center_y)
    building_polygon = Polygon(building_coords)

    # # Check zoning
    zoning_with_building = check_zoning(building_polygon, zoning_map)

    # # Check plot
    building_Plot = check_plot(building_polygon, plot_map)
    ("Plot ID")
    print(building_Plot.R1_EGRIS_E)
    areas = result_from_ata["LeopoldPointBuilding_01.Full_2x3_total_area_net_summary"]["net_area"]

    # Calculate the total area
    total_area = sum(areas.values())

    # Initialize building data dictionary
    building_data = {
        "heighest": result_from_ata["LeopoldPointBuilding_01.Full_2x3_xyz_extremes"]["highest_z"],
        "lowest": result_from_ata["LeopoldPointBuilding_01.Full_2x3_xyz_extremes"]["lowest_z"],
        "number_of_floors": result_from_ata["LeopoldPointBuilding_01.Full_2x3_total_area_net_summary"]["number_of_floors"],
        "total_floor_area": total_area,
        "ground_floor_area": result_from_ata["LeopoldPointBuilding_01.Full_2x3_total_area_net_summary"]["net_area"]["Ground Floor"],
        "facade_length_1": result_from_ata["LeopoldPointBuilding_01.Full_2x3_facade_lengths"]["facade_length_1"],
        "facade_length_2": result_from_ata["LeopoldPointBuilding_01.Full_2x3_facade_lengths"]["facade_length_2"],
        "facade_length_3": result_from_ata["LeopoldPointBuilding_01.Full_2x3_facade_lengths"]["facade_length_3"],
        "facade_length_4": result_from_ata["LeopoldPointBuilding_01.Full_2x3_facade_lengths"]["facade_length_4"],
        "number_of_underground_level": 1,
        "facades": result_from_ata["LeopoldPointBuilding_01.Full_2x3_external_walls"],
        "Plot Area": building_Plot.geometry.area,
        "Georeference": lv95_coords,
        "Centroid": centroid_lv95,
        "Rotation": angle
    }

    floor_area_ratio = building_data["ground_floor_area"]/building_data["Plot Area"]
    building_to_land_area = building_data["total_floor_area"]/building_data["Plot Area"]

    #to be checked or updated:
    fassadelaenge = "nAn"
    Grundgrenzbastand = 5
    UnderGround = 1
    basementMax = 0
    anDGmax = 1

    #Store zoning information if available (only first matching zone)
    #if not zoning_with_building.empty:
    #   print("testing rotation issues")
    first_zone = zoning_with_building  # Take the first matching zoning entry
    fassade_length_list = [result_from_ata["LeopoldPointBuilding_01.Full_2x3_facade_lengths"]["facade_length_1"],result_from_ata["LeopoldPointBuilding_01.Full_2x3_facade_lengths"]["facade_length_2"],result_from_ata["LeopoldPointBuilding_01.Full_2x3_facade_lengths"]["facade_length_3"],result_from_ata["LeopoldPointBuilding_01.Full_2x3_facade_lengths"]["facade_length_4"]]
    building_data.update({
            "OBJID": first_zone['OBJID'],
            "R1_CODE": first_zone['R1_CODE'],
            "R1_BEZEICH": first_zone['R1_BEZEICH'],
            "R1_Abkuerz": first_zone['R1_ABKUERZ'],
            "Plot ID": building_Plot.R1_EGRIS_E.values,
            "Wohnanteil": first_zone['WOHNANTEIL'],
            "Wohnanteil": first_zone['WOHNANTEIL'],
            "getFloorAreaRatio": floor_area_ratio,
            "getBuildingToLandArea": building_to_land_area,
            "Ausnuetzungsziffer Max": first_zone['AUSNUETZU1'],
            "Maximum building length": fassadelaenge,
            "Anrechenbares Untergeschoss max.": basementMax,
            "anrechenbares Dachgeschoss max.": anDGmax,
            "Grundgrenzabstand": Grundgrenzbastand,
            "Fassadelänge max": fassadelaenge,

            #Here come the checks
            "heighest": result_from_ata["LeopoldPointBuilding_01.Full_2x3_xyz_extremes"]["highest_z"],
            "lowest": result_from_ata["LeopoldPointBuilding_01.Full_2x3_xyz_extremes"]["lowest_z"],
            "heights check" : heights_check(result_from_ata["LeopoldPointBuilding_01.Full_2x3_xyz_extremes"]["highest_z"],zoning_with_building.get('GEBAEUDEHO', -99).values[0]),
            "floor_number_check" : floor_number_check(result_from_ata["LeopoldPointBuilding_01.Full_2x3_total_area_net_summary"]["number_of_floors"],zoning_with_building.get('VOLLGESCHO', 0).values[0]),
            "fassade length check" : fassade_length_check(fassade_length_list, fassadelaenge),
            "plot distance check" : grenzabstand_check(building_Plot, boundary_polygon, Grundgrenzbastand),
            #"basement check" : untergeschoss_check( ,basementMax),
            #"building lenght check": building_length_check(),
            #"floor area check": floor_area_Ratio_check()
            



        })

    # # Extract zoning restrictions and add them to building_data
    zoning_restrictions = extract_zoning_restrictions(zoning_with_building)
    building_data.update(zoning_restrictions)  # Merging dictionaries

    # Save data to JSON

    save_to_json(building_data, "building_data.json")
    print("JSON saved successfully:", building_data)

    # # Visualization
    #plot_building_and_zoning(boundary_95_rotated, plot_map, lv95_coords, vertices_95, zoom_factor=2)

    return building_data

def ensure_serializable(obj):
    """ Recursively convert all values to JSON-friendly Python types """
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj  # Already JSON serializable
    elif isinstance(obj, dict):
        return {key: ensure_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [ensure_serializable(item) for item in obj]
    elif hasattr(obj, "tolist"):  # Handle list-like objects
        return obj.tolist()
    return str(obj)  # Convert unknown objects to strings

#Check functions

"""
Comparisons functions

"""
def heights_check(height, max_height):
    if float(height) > float(max_height):
        return False
    else:
        return True


def floor_number_check(floor_number, floor_number_max):
    if float(floor_number) > float(floor_number_max):
        return False
    else:
        return True


def fassade_length_check(fassade_length_list,fassade_length_max):
    if fassade_length_max == "nAn":
        return True
    else:
        for fassade in fassade_length_list:
            if float(fassade) > float(fassade_length_max):
                return False
        return True


def grenzabstand_check(polygon_plot,polygon_building, grenzabstand):
    grenzabstand_polygon = polygon_plot.buffer(-float(grenzabstand))
    return not grenzabstand_polygon.intersects(polygon_building)


def untergeschoss_check(untergeschoss_number,untergeschoss_max):
    if float(untergeschoss_number) > float(untergeschoss_max):
        return False
    else:
        return True

def building_length_check(building_length, building_length_max):
    if building_length != "nAn":
        if float(building_length) > float(building_length_max):
            return False
        else:
            return True
    else:
        return True

def floor_area_Ratio_check(floor_area, floor_area_max):
    if floor_area != float(-99):
        if float(floor_area) > float(floor_area_max):
            return False
        else:
            return True
    else:
        return True


# IFC Test File
path = r"tests/LeopoldPointBuilding_03.Light_IFC4_GL_Zurich_2056_.ifc"

# SHP Zone File
zoning_map_path = r"data\Zonenplan.shp"

# SHP Plot File
plot_map_path = r"data\Plot.shp"


# actual test
if __name__ == "__main__":
    if os.path.exists(path):
        if os.path.exists(zoning_map_path):
            if os.path.exists(plot_map_path):
                result_from_ata = main(path)
                get_Building_data(path, zoning_map_path,result_from_ata,plot_map_path)

        else:
            print("SHP file missing")

    else:
        print("IFC file missing")

UPLOAD_DIR = "uploads"

@app.get("/")
def read_root():
    return {"message": "Ready for AEC Hackaton Zurich 2025 ESRI!"}

@app.post("/upload/")
async def upload_ifc(file: UploadFile = File(...)):
    print(f"Received file: {file.filename}")
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Save the uploaded IFC file
    ifc_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(ifc_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result_from_ata = main(ifc_path)
    building_data = get_Building_data(path, zoning_map_path, result_from_ata, plot_map_path)
    print("This is the final building data: ", building_data)
    #Load the existing SHP file
    if os.path.exists(zoning_map_path):
        try:
            gdf = gpd.read_file(zoning_map_path)
            shp_info = gdf.head().to_json()  # Convert first few rows to JSON
        except Exception as e:
            return {"error": f"Failed to read SHP file: {str(e)}"}
    else:
        return {"error": "SHP file is missing on the server"}

    try:
         building_data = get_Building_data(path, zoning_map_path, result_from_ata, plot_map_path)
         print("This is the final building data: ", building_data)
    except Exception as e:
        return {"error": f"Failed to process IFC file: {str(e)}"}

    # Create the response payload
    response_data = {
        "message": "IFC file uploaded and processed successfully",
        "rhino": json.dumps(ensure_serializable(building_data), indent=4),
        "data": ensure_serializable(building_data),
            # Convert to JSON-safe types
    }

    # Send to Speckle
    speckle_response = await send_to_speckle(response_data, SPECKLE_TOKEN, DATA_ID)
    print("Speckle send complete:", speckle_response)

    response_data["speckle"] = speckle_response

    return response_data






@app.post("/upload-to-speckle/")
async def upload_to_speckle_route(file: UploadFile = File(...)):
    """Endpoint per caricare un file IFC su Speckle con conversione dettagliata"""
    print(f"Received file for Speckle upload: {file.filename}")

    try:
        # Salva il file temporaneamente
        ifc_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(ifc_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        try:
            # Inizializza il convertitore
            converter = IFCToSpeckle(
                speckle_server_url=SPECKLE_SERVER,
                stream_id=STREAM_ID,
                token=SPECKLE_TOKEN
            )

            # Processa e invia a Speckle
            obj_id, commit_id = converter.process_and_send(ifc_path)

            return {
                "message": "File successfully uploaded to Speckle with detailed conversion",
                "data": {
                    "object_id": obj_id,
                    "commit_id": commit_id,
                    "stream_id": STREAM_ID,
                    "file_name": file.filename
                }
            }
        finally:
            # Pulisci il file temporaneo
            if os.path.exists(ifc_path):
                os.remove(ifc_path)
                print(f"Temporary file removed: {ifc_path}")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Speckle upload failed: {str(e)}"
        )
