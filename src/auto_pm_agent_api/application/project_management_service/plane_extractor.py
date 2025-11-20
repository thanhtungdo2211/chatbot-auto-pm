"""Plane extractor for extracting project information from file content."""

import logging
from auto_pm_agent_api.domain.prompts import PROMPT_PLANE_EXTRACT
from auto_pm_agent_api.domain.models import ExtractedPlaneData

logger = logging.getLogger(__name__)


class PlaneExtractor:
    """
    Extractor for converting file content to structured Plane project data.
    
    Uses LLM with structured output to extract project and task information
    from file content (e.g., Excel converted to JSON, text files, etc.).
    """
    
    def __init__(self, llm_client):
        """
        Initialize the plane extractor.
        
        Args:
            llm_client: LLM client for AI operations
        """
        self.llm = llm_client
        
    def extract(self, data: str) -> ExtractedPlaneData:
        """
        Extract project and task information from file content.
        
        Args:
            data: File content as string (JSON, text, etc.)
            
        Returns:
            ExtractedPlaneData object with project and tasks
        """
        try:
            # Build prompt with file content
            prompt = PROMPT_PLANE_EXTRACT.format(file_content=data)
            
            # Generate structured response
            result = self.llm.generate_response(prompt, ExtractedPlaneData)
            
            # Handle list response (some LLMs might return a list)
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
            
            logger.info(f"Extracted project: {result.project.name if result.project else 'None'}")
            logger.info(f"Extracted {len(result.tasks) if result.tasks else 0} tasks")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting plane data: {e}", exc_info=True)
            raise
