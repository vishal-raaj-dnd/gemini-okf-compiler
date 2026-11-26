import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from src.parser import sanitize_slug

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


class OKFMetadata(BaseModel):
    """Structured output schema for OKF concept metadata."""

    type: str = Field(
        description="The OKF category of this document, e.g., 'process', 'guide', 'concept', 'reference', 'standard', 'metric', 'policy'."
    )
    title: str = Field(description="A clean, concise title for this concept.")
    description: str = Field(description="A 1-2 sentence summary of this concept.")
    tags: list[str] = Field(description="A list of 3 to 5 lowercase tags related to the concept.")
    filename: str = Field(
        description="A safe, lowercase kebab-case slug for the filename (no spaces, no extension)."
    )


def create_genai_client(api_key: Optional[str] = None) -> genai.Client:
    """Creates a reusable Gemini API client using the provided key or GEMINI_API_KEY env var."""
    resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not resolved_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")
    return genai.Client(api_key=resolved_key)


def extract_metadata(
    chunk_content: str,
    client: Optional[genai.Client] = None,
    model: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """
    Sends a concept chunk to Gemini to determine its OKF category and metadata.
    Sanitizes returned category and filename slugs to prevent path traversal.
    """
    active_client = client or create_genai_client()
    active_model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL

    prompt = (
        "You are an expert OKF (Open Knowledge Format) curator.\n"
        "Analyze the following document chunk, extract its key concepts, "
        "and structure its metadata according to the requested schema.\n\n"
        f"--- CHUNK START ---\n{chunk_content}\n--- CHUNK END ---\n"
    )

    response = active_client.models.generate_content(
        model=active_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=OKFMetadata,
            temperature=0.1,
        ),
    )

    if not response.text:
        raise ValueError("Gemini API returned an empty response.")

    metadata = OKFMetadata.model_validate_json(response.text)

    safe_type = sanitize_slug(metadata.type, fallback="concept")
    safe_filename = sanitize_slug(metadata.filename, fallback="concept")
    clean_tags = [tag.strip().lower() for tag in metadata.tags if tag.strip()]

    metadata_dict = {
        "type": safe_type,
        "title": metadata.title.strip() or safe_filename,
        "description": metadata.description.strip(),
        "tags": clean_tags if clean_tags else ["general"],
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "filename": safe_filename,
    }

    return metadata_dict, chunk_content
