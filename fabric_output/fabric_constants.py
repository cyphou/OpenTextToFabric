"""Fabric constants — Spark type maps, naming conventions, sanitization."""

from __future__ import annotations

import re

# OpenText/SQL → Spark Delta type mapping
SQL_TO_SPARK_TYPE: dict[str, str] = {
    # String types
    "string": "STRING",
    "varchar": "STRING",
    "nvarchar": "STRING",
    "char": "STRING",
    "nchar": "STRING",
    "text": "STRING",
    "ntext": "STRING",
    "clob": "STRING",
    "nclob": "STRING",
    "longvarchar": "STRING",
    # Integer types
    "int": "INT",
    "integer": "INT",
    "smallint": "SMALLINT",
    "tinyint": "TINYINT",
    "bigint": "BIGINT",
    "long": "BIGINT",
    # Decimal types
    "float": "FLOAT",
    "double": "DOUBLE",
    "decimal": "DECIMAL(18,2)",
    "numeric": "DECIMAL(18,2)",
    "number": "DECIMAL(18,2)",
    "real": "FLOAT",
    "money": "DECIMAL(19,4)",
    # Boolean
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
    "bit": "BOOLEAN",
    # Date/time
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "datetime2": "TIMESTAMP",
    "timestamp": "TIMESTAMP",
    "time": "STRING",
    # Binary
    "binary": "BINARY",
    "varbinary": "BINARY",
    "blob": "BINARY",
    "image": "BINARY",
}

# BIRT data type → Spark type mapping
BIRT_TO_SPARK_TYPE: dict[str, str] = {
    "integer": "INT",
    "float": "FLOAT",
    "double": "DOUBLE",
    "decimal": "DECIMAL(18,2)",
    "string": "STRING",
    "date": "DATE",
    "date-time": "TIMESTAMP",
    "time": "STRING",
    "boolean": "BOOLEAN",
    "any": "STRING",
    "blob": "BINARY",
}

# BIRT data type → DAX data type
BIRT_TO_DAX_TYPE: dict[str, str] = {
    "integer": "Int64.Type",
    "float": "Double.Type",
    "double": "Double.Type",
    "decimal": "Decimal.Type",
    "string": "Text.Type",
    "date": "Date.Type",
    "date-time": "DateTime.Type",
    "time": "Time.Type",
    "boolean": "Logical.Type",
    "any": "Text.Type",
}

# BIRT data type → TMDL data type
BIRT_TO_TMDL_TYPE: dict[str, str] = {
    "integer": "int64",
    "float": "double",
    "double": "double",
    "decimal": "decimal",
    "string": "string",
    "date": "dateTime",
    "date-time": "dateTime",
    "time": "dateTime",
    "boolean": "boolean",
    "any": "string",
}

# Power Query M type mapping
BIRT_TO_M_TYPE: dict[str, str] = {
    "integer": "Int64.Type",
    "float": "Number.Type",
    "double": "Number.Type",
    "decimal": "Number.Type",
    "string": "Text.Type",
    "date": "Date.Type",
    "date-time": "DateTime.Type",
    "time": "Time.Type",
    "boolean": "Logical.Type",
    "any": "Any.Type",
}


def sanitize_name(name: str, max_length: int = 128) -> str:
    """Sanitize a name for use in Fabric artifacts (Lakehouse, tables, columns)."""
    # Replace special characters with underscores
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)
    # Strip leading/trailing underscores
    safe = safe.strip("_")
    # Ensure starts with letter or underscore
    if safe and safe[0].isdigit():
        safe = f"_{safe}"
    # Limit length
    if len(safe) > max_length:
        safe = safe[:max_length]
    return safe or "unnamed"


def sanitize_table_name(name: str) -> str:
    """Sanitize for Delta table name (lowercase, snake_case)."""
    return sanitize_name(name).lower()


def sanitize_column_name(name: str) -> str:
    """Sanitize for Delta table column name."""
    return sanitize_name(name)


def spark_type(source_type: str) -> str:
    """Convert source data type to Spark Delta type."""
    key = source_type.lower().strip()
    # Handle parameterized types like varchar(255)
    base = key.split("(")[0].strip()
    return SQL_TO_SPARK_TYPE.get(base, "STRING")
