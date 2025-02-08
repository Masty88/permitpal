import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.selector
import ifcopenshell.geom
import json
import time
import os
import argparse

start_time = time.time()

def process_ifc_file(ifc_file_path):
    start_time = time.time()

    model = ifcopenshell.open(ifc_file_path)

    ifc_classes_to_process = [
        "IfcWallStandardCase",
        "IfcWall"
    ]

    external_wall_globalids = []

    for ifc_class in ifc_classes_to_process:
        entities = model.by_type(ifc_class)
        for entity in entities:
            info = entity.get_info()  
            psets = ifcopenshell.util.element.get_psets(entity) 
            if "Pset_WallCommon" in psets:
                pset_common = psets["Pset_WallCommon"]
                # Check if the wall is marked as external
                if pset_common.get("IsExternal", False) is True:
                    global_id = info.get("GlobalId")
                    if global_id:
                        external_wall_globalids.append(global_id)

    external_wall_globalids = list(set(external_wall_globalids))

    base_name = os.path.splitext(os.path.basename(ifc_file_path))[0]
    output_file = os.path.join(os.path.dirname(ifc_file_path), f"results/{base_name}_external_walls.json")

    # Write the list of GlobalIds to a JSON file.
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(external_wall_globalids, f, indent=4, ensure_ascii=False)

    print(f"Saved external wall GlobalIds to {output_file}")
    end_time = time.time()
    latency = end_time - start_time
    print("Latency:", latency)

def main():
    parser = argparse.ArgumentParser(
        description="Extract GlobalIds of external walls (IfcWallStandardCase/IfcWall) from an IFC file."
    )
    parser.add_argument(
        "ifc_file",
        help="Path to the IFC file to process."
    )
    args = parser.parse_args()
    process_ifc_file(args.ifc_file)

if __name__ == '__main__':
    main()
