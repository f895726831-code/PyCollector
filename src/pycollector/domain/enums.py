"""
Core domain error codes.

Extend this enum in your application to add domain-specific error codes.
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    """Generic error codes for web data collection systems."""

    # Entity / resource errors
    INVALID_ENTITY_CODE = "INVALID_ENTITY_CODE"
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"

    # Request errors
    INVALID_QUERY_PARAM = "INVALID_QUERY_PARAM"

    # Collection errors
    SOURCE_FETCH_FAILED = "SOURCE_FETCH_FAILED"
    PARSE_RESULT_EMPTY = "PARSE_RESULT_EMPTY"
    PARSE_CONFLICT = "PARSE_CONFLICT"

    # Write errors
    BUSINESS_WRITE_FAILED = "BUSINESS_WRITE_FAILED"

    # System errors
    INTERNAL_ERROR = "INTERNAL_ERROR"