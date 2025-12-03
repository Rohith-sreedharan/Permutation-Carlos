"""
MongoDB Helper Utilities
Functions to clean MongoDB documents for JSON serialization
"""
from typing import Any, Dict, List, Union
from bson import ObjectId


def sanitize_mongo_doc(doc: Any) -> Any:
    """
    Recursively remove MongoDB-specific fields (_id, ObjectId) from documents
    to make them JSON serializable.
    
    Args:
        doc: MongoDB document, list, dict, or primitive value
        
    Returns:
        Sanitized version safe for JSON serialization
    """
    if doc is None:
        return None
    
    # Handle ObjectId directly
    if isinstance(doc, ObjectId):
        return str(doc)
    
    # Handle dictionaries (MongoDB documents)
    if isinstance(doc, dict):
        cleaned = {}
        for key, value in doc.items():
            # Skip _id field entirely (or convert to string if needed)
            if key == "_id":
                continue  # Remove _id completely
            else:
                cleaned[key] = sanitize_mongo_doc(value)
        return cleaned
    
    # Handle lists
    if isinstance(doc, list):
        return [sanitize_mongo_doc(item) for item in doc]
    
    # Handle tuples (convert to list)
    if isinstance(doc, tuple):
        return [sanitize_mongo_doc(item) for item in doc]
    
    # Primitives pass through
    return doc


def sanitize_mongo_list(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sanitize a list of MongoDB documents
    
    Args:
        docs: List of MongoDB documents
        
    Returns:
        List of sanitized documents
    """
    return [sanitize_mongo_doc(doc) for doc in docs]
