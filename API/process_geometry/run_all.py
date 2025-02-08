import argparse
import subprocess
import sys
import os
import glob
import json

def cleanup_results_folder(results_folder="./uploads/results"):
    if not os.path.exists(results_folder):
        os.makedirs(results_folder)
        print(f"Created results folder: {results_folder}")
    else:
        files = glob.glob(os.path.join(results_folder, "*"))
        for f in files:
            try:
                os.remove(f)
                print(f"Deleted file: {f}")
            except Exception as e:
                print(f"Error deleting file {f}: {e}")

def create_cumulative_json(ifc_file, results_folder="./uploads/results"):
    base_name = os.path.splitext(os.path.basename(ifc_file))[0]
    output_file = f"./uploads/{base_name}.json"
    cumulative_data = {}

    json_pattern = os.path.join(results_folder, "*.json")
    json_files = glob.glob(json_pattern)
    
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                key = os.path.splitext(os.path.basename(json_file))[0]
                cumulative_data[key] = data
        except Exception as e:
            print(f"Error reading {json_file}: {e}")

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(cumulative_data, f, indent=4)
        # print(f"Cumulative JSON file created: {output_file}")
    except Exception as e:
        print(f"Error writing the cumulative JSON file: {e}")

    return output_file

def main(ifc_path):
    ifc_file = ifc_path

    print("Cleaning up the results folder...")
    cleanup_results_folder("./uploads/results")

    print("Running detect_space.py ...")
    result1 = subprocess.run([sys.executable, "./process_geometry/detect_space.py", ifc_file])
    if result1.returncode != 0:
        print("Error: detect_space.py did not complete successfully.")
        sys.exit(result1.returncode)

    print("Running extreme_x_y_z.py ...")
    result2 = subprocess.run([sys.executable, "./process_geometry/extreme_x_y_z.py", ifc_file])
    if result2.returncode != 0:
        print("Error: extreme_x_y_z.py did not complete successfully.")
        sys.exit(result2.returncode)

    print("Running facade walls (get_ext_walls_id.py) ...")
    result3 = subprocess.run([sys.executable, "./process_geometry/get_ext_walls_id.py", ifc_file])
    if result3.returncode != 0:
        print("Error: get_ext_walls_id.py did not complete successfully.")
        sys.exit(result3.returncode)

    print("All scripts completed successfully.")

    cumulative_filename = create_cumulative_json(ifc_file, "./uploads/results")

    cumulative_json = {}
    try:
        with open(cumulative_filename, "r", encoding="utf-8") as f:
            cumulative_json = json.load(f)
        # Optionally print the cumulative JSON when run from the command line.
        # print("\nCumulative JSON content:")
        # print(json.dumps(cumulative_json, indent=4))
    except Exception as e:
        print(f"Error reading cumulative JSON file: {e}")

    return cumulative_json


if __name__ == "__main__":
    ifc_path = "LeopoldPointBuilding_01.Full_2x3.ifc"
    result = main(ifc_path)
