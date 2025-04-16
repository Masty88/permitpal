# AEC Hackathon Zurich 2025 - Building Data Analysis Tool ⚠️ ALPHA - WORK IN PROGRESS ⚠️

## Project Overview

This project addresses the ETH Zurich challenge "from 2D to CO2" - automating the analysis of building data to calculate CO2 footprints. Our solution extracts data from IFC building models, analyzes them against zoning regulations, and provides visualization of building properties and their environmental impact.

![AEC Hackathon](https://aechackathon.com/wp-content/uploads/2023/06/aec-hackathon-logo-300x67.png)

## Features

- IFC file upload and analysis
- Extraction of building data (height, floors, area)
- Zoning regulation compliance checking with AI-powered analysis
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

### Configuration

**Important Note:** The application requires configuration of the following tokens:

1. **Speckle Token**: Required for 3D model visualization and collaboration
   - The current code contains a placeholder token in `main.py`:
     ```python
     SPECKLE_TOKEN = ""  # Replace with your token
     STREAM_ID = "ac4a00b20e"  # Replace with your stream ID
     ```
   - You will need to replace this with your own valid Speckle token and stream ID

2. **OpenAI API Key**: Required for the compliance checking functionality
   - The project uses Langchain with OpenAI for analyzing building compliance with regulations
   - You'll need to create a `.env` file in the root directory and add your OpenAI API key:
     ```
     OPENAI_API_KEY=your_openai_api_key_here
     ```
   - The code uses `load_dotenv()` to securely load this key from the .env file

Please ensure all tokens are properly configured before running the application.

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
   - **Note:** The application is currently tested with and configured for specific test files:
     - `LeopoldPointBuilding_01.Full_IFC4_GL_Zurich_2056.ifc`
     - `LeopoldPointBuilding_03.Light_IFC4_GL_Zurich_2056.ifc`
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
- **AI & NLP**: OpenAI, Langchain for intelligent compliance checking
- **JavaScript/TypeScript**: Astro, React
- **3D Visualization**: Speckle
- **Data Processing**: Apollo GraphQL for subscription management

## Project Structure

```
├── API/
│   ├── main.py                  # FastAPI backend
│   ├── speckle_transform.py     # Speckle integration
│   ├── uploads/                 # Uploaded files directory
│   ├── tests/                   # Test files directory
│   │   ├── LeopoldPointBuilding_01.Full_IFC4_GL_Zurich_2056.ifc
│   │   └── LeopoldPointBuilding_03.Light_IFC4_GL_Zurich_2056.ifc
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
- Used AI to analyze building compliance with zoning regulations
- Automated assessment of CO2 impact based on building properties

## Future Improvements

- Enhanced CO2 calculation based on material properties
- Visualization of retrofitting potential
- Timeline visualization of carbon emissions over building lifecycle
- Integration with more data sources (maintenance logs, material specifications)

## Team

- [Emanuele Mastaglia](https://github.com/Masty88)
- [Mikel Martinez](https://github.com/Mikel0M)
- [Nickolas Maslarinos](https://github.com/nmaslarinos)
- [Alp Okan Atakan](https://www.linkedin.com/in/alpokanatakan/)
- [Niloofar Imani](https://www.linkedin.com/in/niloofarimani/)
- [Atacan Kural Avgören](https://www.linkedin.com/in/atacan-kural-avg%C3%B6ren-ba7a0314b/)
- [Duhan Koyuncu](https://www.linkedin.com/in/oduhan/)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Esri R&D Zurich for challenge inspiration
- AEC Hackathon organizers and sponsors
- Speckle for providing 3D visualization capabilities