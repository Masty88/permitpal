from specklepy.objects import Base
from specklepy.api.client import SpeckleClient
from specklepy.transports.server import ServerTransport
from specklepy.api import operations


async def send_to_speckle(analysis_data, speckle_token, stream_id):
    """
    Create a Speckle Base object from the analysis response data and send it
    """
    # Create main base object
    analysis_base = Base()
    analysis_base.name = "Building Analysis Results"

    # Add all analysis data as properties
    for key, value in analysis_data.items():
        analysis_base[key] = value

    # Initialize Speckle client
    client = SpeckleClient(host="https://app.speckle.systems")
    client.authenticate_with_token(token=speckle_token)

    # Create transport
    transport = ServerTransport(client=client, stream_id=stream_id)

    # Send the analysis base to Speckle
    obj_id = operations.send(base=analysis_base, transports=[transport])

    # Create a commit with the analysis results
    commit_id = client.commit.create(
        stream_id=stream_id,
        object_id=obj_id,
        message="Building Analysis Results"
    )

    return {
        "object_id": obj_id,
        "commit_id": commit_id,
        "stream_id": stream_id
    }