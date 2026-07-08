import os
from datetime import datetime
from typing import Dict, Any, Tuple
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Define the structured output schema for OKF metadata
class OKFMetadata(BaseModel):
    type: str = Field(
        description="The OKF category of this document, e.g., 'process', 'guide', 'concept', 'reference', 'standard', 'metric', 'policy'."
    )
    title: str = Field(
        description="A clean, concise title for this concept."
    )
    description: str = Field(
        description="A 1-2 sentence summary of this concept."
    )
    tags: list[str] = Field(
        description="A list of 3 to 5 lowercase tags related to the concept."
    )
    filename: str = Field(
        description="A safe, lowercase kebab-case slug for the filename (no spaces, no extension, e.g., 'onboarding-process' or 'db-schema')."
    )

def extract_metadata(chunk_content: str) -> Tuple[Dict[str, Any], str]:
    """
    Sends a concept chunk to Gemini Flash to determine its category and metadata.
    
    Returns:
        A tuple of (metadata_dict, cleaned_markdown_body)
    """
    # The SDK automatically uses the GEMINI_API_KEY environment variable.
    # If not set, it will raise an error.
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it in your .env file.")
        
    client = genai.Client(api_key=api_key)
    
    prompt = (
        "You are an expert OKF (Open Knowledge Format) curator.\n"
        "Analyze the following document chunk, extract its key concepts, "
        "and structure its metadata according to the requested schema.\n\n"
        f"--- CHUNK START ---\n{chunk_content}\n--- CHUNK END ---\n"
    )
    
    # Generate content with structured JSON output matching the Pydantic model
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=OKFMetadata,
            temperature=0.1
        )
    )
    
    # Parse the structured response
    metadata = OKFMetadata.model_validate_json(response.text)
    
    # Prepare the metadata dictionary for YAML conversion
    metadata_dict = {
        "type": metadata.type.strip().lower(),
        "title": metadata.title.strip(),
        "description": metadata.description.strip(),
        "tags": [tag.strip().lower() for tag in metadata.tags],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "filename": metadata.filename.strip().lower()
    }
    
    return metadata_dict, chunk_content
