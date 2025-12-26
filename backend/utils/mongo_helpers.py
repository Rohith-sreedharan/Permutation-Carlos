"""
MongoDB Helper Utilities
Functions to clean MongoDB documents for JSON serialization
"""
from typing import Any, Dict, List, Union
from bson import ObjectId
import numpy as np


def sanitize_mongo_doc(doc: Any) -> Any:
    """
    Recursively remove MongoDB-specific fields (_id, ObjectId) from documents
    to make them JSON serializable. Also converts numpy types to native Python types.
    
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
    
    # Handle numpy types - check type name first for broader compatibility
    type_name = type(doc).__name__
    if type_name.startswith('bool') or 'bool' in type_name.lower():
        # Handles np.bool_, np.False_, np.True_, etc.
        return bool(doc)
    if type_name.startswith('int') or type_name in ['int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64']:
        return int(doc)
    if type_name.startswith('float') or type_name in ['float16', 'float32', 'float64', 'float128']:
        return float(doc)
    
    # Handle numpy arrays
    if isinstance(doc, np.ndarray):
        return doc.tolist()
    
    # Catch-all for any numpy scalar using hasattr and isinstance
    try:
        if hasattr(np, 'generic') and isinstance(doc, np.generic):
            return doc.item()
    except (TypeError, AttributeError):
        pass
    
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
