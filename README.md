# AEC Hackathon Zurich 2025 - Building Data Analysis Tool

## Project Overview

This project addresses the ETH Zurich challenge "from 2D to CO2" - automating the analysis of building data to calculate CO2 footprints. Our solution extracts data from IFC building models, analyzes them against zoning regulations, and provides visualization of building properties and their environmental impact.

![AEC Hackathon](https://aechackathon.com/wp-content/uploads/2023/06/aec-hackathon-logo-300x67.png)

## Features

- IFC file upload and analysis
- Extraction of building data (height, floors, area)
- Zoning regulation compliance checking
- CO2 footprint calculation
- Data visualization through interactive 3D models
- Speckle integration for real-time collaboration

## Architecture

The project consists of:

1. **Backend (Python FastAPI)**
   - IFC file processing with `ifcopenshell`
   - Geospatial analysis with `geopandas`
   - Building data extraction and analysis
   - Speckle integration for 3D model sharing

2. **Frontend (Astro)**
   - File upload interface
   - Results visualization
   - Interactive 3D model viewer

## Installation

### Prerequisites

- Python 3.9+
- Node.js 18+
- Speckle account for 3D visualization

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/aec-hackathon-2025.git
cd aec-hackathon-2025

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server
cd API
uvicorn main:app --reload
```

### Frontend Setup

```bash
# Install dependencies
cd client
npm install

# Start the development server
npm run dev
```

## Usage

1. Open your browser and navigate to `http://localhost:4321`
2. Upload an IFC file using the web interface
3. Choose between "Analyze IFC" or "Upload to Speckle"
4. View the analysis results including:
   - Building height and number of floors
   - Floor area
   - Zoning compliance
   - CO2 footprint estimation

## API Endpoints

- **POST /upload/** - Upload and analyze an IFC file
- **POST /upload-to-speckle/** - Upload an IFC file to Speckle for 3D visualization

## Technologies Used

- **Python**: FastAPI, ifcopenshell, geopandas, matplotlib
- **JavaScript/TypeScript**: Astro, React
- **3D Visualization**: Speckle
- **Data Processing**: Apollo GraphQL for subscription management

## Project Structure

```
├── API/
│   ├── main.py                  # FastAPI backend
│   ├── speckle_transform.py     # Speckle integration
│   ├── uploads/                 # Uploaded files directory
│   └── data/                    # Zoning data
│       └── Zonenplan.shp        # Zoning regulations
│
├── client/
│   ├── src/
│   │   ├── pages/
│   │   │   └── upload.astro     # Frontend upload page
│   │   └── components/
│   └── public/
│
└── README.md                    # Project documentation
```

## Challenges Addressed

From the ETH Zurich challenge "from 2D to CO2":
- Extracted building components from building documentation
- Created spatial visualizations of embodied carbon
- Built data integration pipelines connecting various data sources

## Future Improvements

- Enhanced CO2 calculation based on material properties
- Visualization of retrofitting potential
- Timeline visualization of carbon emissions over building lifecycle
- Integration with more data sources (maintenance logs, material specifications)

## Team

- [Team Member 1] - Role
- [Team Member 2] - Role
- [Team Member 3] - Role

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- ETH Zurich Digital Twin Program for the challenge inspiration
- AEC Hackathon organizers and sponsors
- Speckle for providing 3D visualization capabilities