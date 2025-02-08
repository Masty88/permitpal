from specklepy.api.client import SpeckleClient
from specklepy.transports.server import ServerTransport
from specklepy.api import operations
from specklepy.objects import Base
from specklepy.objects.geometry import Mesh, Box
import ifcopenshell
import ifcopenshell.geom


class IFCToSpeckle:
    def __init__(self, speckle_server_url, token, stream_id=None):
        self.client = SpeckleClient(host=speckle_server_url)
        self.client.authenticate_with_token(token)

        if stream_id is None:
            new_stream = self.client.stream.create(
                name="IFC Upload Stream",
                description="Automatically created stream for IFC uploads"
            )
            self.stream_id = new_stream.id
            print(f"Created new stream with ID: {self.stream_id}")
        else:
            self.stream_id = stream_id

        self.transport = ServerTransport(client=self.client, stream_id=self.stream_id)

    def extract_properties(self, ifc_element):
        props = Base()
        props["global_id"] = ifc_element.GlobalId
        props["name"] = ifc_element.Name if hasattr(ifc_element, 'Name') else "Unnamed Element"
        props["ifcType"] = ifc_element.is_a()
        props["ObjectType"] = ifc_element.ObjectType if hasattr(ifc_element, 'ObjectType') else "N/A"
        props["Tag"] = ifc_element.Tag if hasattr(ifc_element, 'Tag') else "N/A"
        props["expressID"] = ifc_element.id()

        if hasattr(ifc_element, "HasPropertySets"):
            props["PropertySets"] = {}
            for pset in ifc_element.HasPropertySets:
                if hasattr(pset, "Name") and hasattr(pset, "HasProperties"):
                    pset_name = pset.Name
                    props["PropertySets"][pset_name] = {}
                    for prop in pset.HasProperties:
                        prop_name = prop.Name
                        prop_value = prop.NominalValue.wrappedValue if hasattr(prop.NominalValue, 'wrappedValue') else prop.NominalValue
                        props["PropertySets"][pset_name][prop_name] = prop_value

        return props

    def extract_geometry(self, ifc_element):
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)

        try:
            shape = ifcopenshell.geom.create_shape(settings, ifc_element)
            geometry = shape.geometry
            vertices = geometry.verts
            faces = geometry.faces

            if len(vertices) == 0 or len(faces) == 0:
                print(f"No geometry for element {ifc_element.GlobalId}")
                return None

            # Creazione della lista delle facce
            speckle_faces = []
            for i in range(0, len(faces), 3):
                speckle_faces.append(3)  # Il numero 3 indica una faccia triangolare
                speckle_faces.extend([faces[i], faces[i+1], faces[i+2]])

            mesh_area = 0.0  # Placeholder per il calcolo dell'area
            speckle_mesh = Mesh(
                vertices=list(vertices),
                faces=speckle_faces,
                colors=[],
                textureCoordinates=[],
                units="millimeters",
                area=mesh_area,
                bbox=Box(area=0.0, volume=0.0),
            )

            print(f"Mesh for element {ifc_element.GlobalId}: vertices={len(vertices)}, faces={len(faces)//3}")
            return speckle_mesh
        except Exception as e:
            print(f"Error extracting geometry for {ifc_element.GlobalId}: {e}")
            return None

    def process_and_send(self, ifc_path):
        ifc_file = ifcopenshell.open(ifc_path)

        speckle_base = Base()
        speckle_base.name = "IFC Model"
        speckle_base["collectionType"] = "model"

        project = Base()
        project.name = "IFC Project"
        project.speckle_type = "IFCProject"

        site = Base()
        site.name = "Site"
        site.speckle_type = "IFCSite"

        building = Base()
        building.name = "Unnamed Building"
        building.speckle_type = "IFCBuilding"

        storeys = {}

        for element in ifc_file.by_type("IfcProduct"):
            element_base = Base()

            properties = self.extract_properties(element)
            for key in properties.get_dynamic_member_names():
                element_base[key] = properties[key]

            element_base.speckle_type = properties["ifcType"]

            geometry = self.extract_geometry(element)
            if geometry:
                element_base["displayValue"] = [geometry]
            else:
                print(f"Element {element.GlobalId} does not have valid geometry, but properties were added.")

            if hasattr(element, "ContainedInStructure"):
                for rel in element.ContainedInStructure:
                    if rel.is_a("IfcRelContainedInSpatialStructure") and rel.RelatingStructure.is_a("IfcBuildingStorey"):
                        storey_id = rel.RelatingStructure.GlobalId
                        if storey_id not in storeys:
                            storey_base = Base()
                            storey_base.name = rel.RelatingStructure.Name if rel.RelatingStructure.Name else "Unnamed Storey"
                            storey_base.speckle_type = "IFCBuildingStorey"
                            storey_base["global_id"] = storey_id
                            storey_base["elements"] = []
                            storeys[storey_id] = storey_base

                        storeys[storey_id]["elements"].append(element_base)

        building["elements"] = list(storeys.values())
        site["elements"] = [building]
        project["elements"] = [site]
        speckle_base["elements"] = [project]

        object_id = operations.send(base=speckle_base, transports=[self.transport])
        print(f"Object ID sent: {object_id}")

        commit_id = self.client.commit.create(
            stream_id=self.stream_id,
            object_id=object_id,
            message="Uploaded IFC model with correct Speckle types and geometry"
        )
        print(f"Commit ID: {commit_id}")

        return object_id, commit_id