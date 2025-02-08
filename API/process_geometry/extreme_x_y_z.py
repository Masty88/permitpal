import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.selector
import ifcopenshell.geom
import numpy as np
import json
import time
import os
import argparse
import math  # Needed for distance calculations

start_time = time.time()

# --- EXTREME COORDINATE EXTRACTION ---

def extract_xyz_extremes(ifc_entities_clean):
    """
    Loop through all IFC entities and extract the overall lowest and highest
    x, y, and z values from their bounding boxes.
    Returns a dictionary containing only the extreme values.
    """
    lowest_x = float("inf")
    highest_x = float("-inf")
    lowest_y = float("inf")
    highest_y = float("-inf")
    lowest_z = float("inf")
    highest_z = float("-inf")

    for ifc_class, entities in ifc_entities_clean.items():
        for entity_id, entity in entities.items():
            geometry = entity.get("geometry", {})
            bbox = geometry.get("bounding_box", None)
            # Skip if bounding box is missing or invalid.
            if bbox is None or not isinstance(bbox, dict):
                continue

            min_coords = bbox.get("min", [])
            max_coords = bbox.get("max", [])

            if len(min_coords) >= 3:
                # Check lowest values from the minimum corner.
                x_val = min_coords[0]
                y_val = min_coords[1]
                z_val = min_coords[2]
                if x_val < lowest_x:
                    lowest_x = x_val
                if y_val < lowest_y:
                    lowest_y = y_val
                if z_val < lowest_z:
                    lowest_z = z_val

            if len(max_coords) >= 3:
                # Check highest values from the maximum corner.
                x_val = max_coords[0]
                y_val = max_coords[1]
                z_val = max_coords[2]
                if x_val > highest_x:
                    highest_x = x_val
                if y_val > highest_y:
                    highest_y = y_val
                if z_val > highest_z:
                    highest_z = z_val

    return {
        "lowest_x": lowest_x,
        "highest_x": highest_x,
        "lowest_y": lowest_y,
        "highest_y": highest_y,
        "lowest_z": lowest_z,
        "highest_z": highest_z
    }

# --- NEW FUNCTION: CALCULATE FACADE LENGTHS ---

def calculate_facade_lengths(extremes):
    """
    Given the extreme x and y values (from extract_xyz_extremes),
    compute the distances between the four corner points of the rectangle:
    
      A = (lowest_x, lowest_y)
      B = (highest_x, lowest_y)
      C = (highest_x, highest_y)
      D = (lowest_x, highest_y)
      
    The function returns a dictionary with four facade lengths:
      - facade_length_1: distance between A and B
      - facade_length_2: distance between B and C
      - facade_length_3: distance between C and D
      - facade_length_4: distance between D and A
    """
    A = (extremes["lowest_x"], extremes["lowest_y"])
    B = (extremes["highest_x"], extremes["lowest_y"])
    C = (extremes["highest_x"], extremes["highest_y"])
    D = (extremes["lowest_x"], extremes["highest_y"])

    facade_length_1 = math.hypot(B[0] - A[0], B[1] - A[1])
    facade_length_2 = math.hypot(C[0] - B[0], C[1] - B[1])
    facade_length_3 = math.hypot(D[0] - C[0], D[1] - C[1])
    facade_length_4 = math.hypot(A[0] - D[0], A[1] - D[1])

    return {
        "facade_length_1": facade_length_1,
        "facade_length_2": facade_length_2,
        "facade_length_3": facade_length_3,
        "facade_length_4": facade_length_4
    }

# --- UTILITY FUNCTIONS FOR JSON SERIALIZATION ---

def remove_duplicate_entities(ifc_entities):
    seen = set()
    new_entities = {}
    for ifc_class, entities in ifc_entities.items():
        new_class_entities = {}
        for entity_id, data in entities.items():
            if entity_id not in seen:
                seen.add(entity_id)
                new_class_entities[entity_id] = data
        new_entities[ifc_class] = new_class_entities
    return new_entities

def sanitize_ifc_data(obj):
    """Recursively convert non-JSON-serializable objects (e.g., IFC entities)
    to strings or basic types."""
    if isinstance(obj, dict):
        return {k: sanitize_ifc_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_ifc_data(e) for e in obj]
    elif isinstance(obj, ifcopenshell.entity_instance):
        return str(obj)
    else:
        return obj

# --- GEOMETRY UTILS ---

geom_settings = ifcopenshell.geom.settings()
geom_settings.set(geom_settings.USE_WORLD_COORDS, True)

def compute_bounding_box(shape):
    vertices = np.array(shape.geometry.verts)
    if vertices.size == 0:
        raise ValueError("No vertices found in geometry.")
    points = vertices.reshape((-1, 3))
    min_coords = points.min(axis=0)
    max_coords = points.max(axis=0)
    # Convert numpy arrays to lists for JSON serialization.
    return {"min": min_coords.tolist(), "max": max_coords.tolist()}

def extract_geometry(entity):
    geometry_data = {}
    try:
        shape = ifcopenshell.geom.create_shape(geom_settings, entity)
        try:
            bbox = compute_bounding_box(shape)
            geometry_data["bounding_box"] = bbox
        except Exception as bb_error:
            geometry_data["bounding_box"] = f"Error computing bounding box: {bb_error}"
    except Exception as e:
        geometry_data["error"] = f"Geometry extraction failed: {e}"
    return geometry_data

# --- MAIN PROCESSING FUNCTION ---

def process_ifc_file(ifc_file_path):
    """Process the IFC file and output JSON files with the extracted data."""
    start_time = time.time()

    # Open the IFC model
    model = ifcopenshell.open(ifc_file_path)

    # List of IFC classes you want to process.
    ifc_classes_to_process = [
        "IfcWall",
        "IfcWallStandardCase",
        "IfcSlab"
    ]

    # Container for storing IFC data.
    IFC_ENTITIES = {}

    for ifc_class in ifc_classes_to_process:
        entities = model.by_type(ifc_class)
        IFC_ENTITIES[ifc_class] = {}

        for entity in entities:
            info = entity.get_info()  # Basic attributes of the entity.
            # Extract the unique identifier.
            entity_id = info.get("id", str(entity))
            geometry = extract_geometry(entity)
            entity_dict = {
                "info": info,
                "geometry": geometry
            }
            IFC_ENTITIES[ifc_class][entity_id] = entity_dict

    IFC_ENTITIES = remove_duplicate_entities(IFC_ENTITIES)
    # --- SANITIZE THE DATA FOR JSON ---
    IFC_ENTITIES_CLEAN = sanitize_ifc_data(IFC_ENTITIES)

    # Determine the base name for output files.
    base_name = os.path.splitext(os.path.basename(ifc_file_path))[0]

    # --- EXTRACT EXTREME VALUES FOR x, y, and z ---
    xyz_extremes = extract_xyz_extremes(IFC_ENTITIES_CLEAN)
    output_file_xyz = os.path.join(os.path.dirname(ifc_file_path), f"results/{base_name}_xyz_extremes.json")
    with open(output_file_xyz, "w", encoding="utf-8") as f:
        json.dump(xyz_extremes, f, indent=4, ensure_ascii=False)
    print(f"Saved extreme coordinate values to {output_file_xyz}")

    # --- CALCULATE FACADE LENGTHS ---
    facade_lengths = calculate_facade_lengths(xyz_extremes)
    output_file_facade = os.path.join(os.path.dirname(ifc_file_path), f"results/{base_name}_facade_lengths.json")
    with open(output_file_facade, "w", encoding="utf-8") as f:
        json.dump(facade_lengths, f, indent=4, ensure_ascii=False)
    print(f"Saved facade lengths to {output_file_facade}")

    end_time = time.time()
    latency = end_time - start_time
    print("Latency:", latency)

def main():
    parser = argparse.ArgumentParser(
        description="Process an IFC file and output its entities with extreme coordinate values and facade lengths as JSON files."
    )
    parser.add_argument(
        "ifc_file",
        help="Path to the IFC file to process."
    )
    args = parser.parse_args()
    process_ifc_file(args.ifc_file)

if __name__ == '__main__':
    main()
