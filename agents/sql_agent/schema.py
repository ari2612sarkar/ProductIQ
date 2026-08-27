"""
Schema introspection tools for SQL Agent.
Retrieves table schemas, columns, foreign keys, and sample data.
"""
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from db.connection import get_readonly_session


@dataclass
class ColumnInfo:
    name: str
    type: str
    nullable: bool
    default: str | None
    primary_key: bool
    foreign_key: str | None
    comment: str | None


@dataclass
class TableInfo:
    name: str
    schema: str
    columns: list[ColumnInfo]
    row_count: int | None = None
    comment: str | None = None
    indexes: list[str] = None


@dataclass
class SchemaInfo:
    tables: dict[str, TableInfo]
    relationships: list[dict[str, str]]


def get_all_tables(schema: str = "public") -> list[str]:
    """Get all table names in a schema."""
    with get_readonly_session() as session:
        result = session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = :schema 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """), {"schema": schema})
        return [row[0] for row in result]


def get_table_info(table_name: str, schema: str = "public") -> TableInfo | None:
    """Get detailed information about a table."""
    with get_readonly_session() as session:
        # Get columns
        cols_result = session.execute(text("""
            SELECT 
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END as is_pk,
                fk.foreign_table_name,
                fk.foreign_column_name,
                col_description(pgc.oid, c.ordinal_position) as comment
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT kcu.column_name, kcu.table_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = :schema
                AND tc.table_name = :table
            ) pk ON c.column_name = pk.column_name
            LEFT JOIN (
                SELECT 
                    kcu.column_name,
                    ccu.table_name as foreign_table_name,
                    ccu.column_name as foreign_column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = :schema
                AND tc.table_name = :table
            ) fk ON c.column_name = fk.column_name
            LEFT JOIN pg_class pgc ON pgc.relname = c.table_name
            WHERE c.table_schema = :schema
            AND c.table_name = :table
            ORDER BY c.ordinal_position
        """), {"schema": schema, "table": table_name})

        columns = []
        for row in cols_result:
            fk = None
            if row.foreign_table_name:
                fk = f"{row.foreign_table_name}.{row.foreign_column_name}"

            columns.append(ColumnInfo(
                name=row.column_name,
                type=row.data_type,
                nullable=row.is_nullable == "YES",
                default=row.column_default,
                primary_key=row.is_pk,
                foreign_key=fk,
                comment=row.comment,
            ))

        # Get row count (approximate)
        count_result = session.execute(text("""
            SELECT reltuples::bigint as estimate 
            FROM pg_class 
            WHERE relname = :table
        """), {"table": table_name})
        row_count = count_result.scalar()

        # Get indexes
        idx_result = session.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = :schema 
            AND tablename = :table
        """), {"schema": schema, "table": table_name})
        indexes = [row[0] for row in idx_result]

        return TableInfo(
            name=table_name,
            schema=schema,
            columns=columns,
            row_count=row_count,
            indexes=indexes,
        )


def get_schema_info(schema: str = "public") -> SchemaInfo:
    """Get complete schema information."""
    tables = {}
    relationships = []

    table_names = get_all_tables(schema)
    for table_name in table_names:
        table_info = get_table_info(table_name, schema)
        if table_info:
            tables[table_name] = table_info

            # Extract relationships
            for col in table_info.columns:
                if col.foreign_key:
                    relationships.append({
                        "source_table": table_name,
                        "source_column": col.name,
                        "target_table": col.foreign_key.split(".")[0],
                        "target_column": col.foreign_key.split(".")[1],
                    })

    return SchemaInfo(tables=tables, relationships=relationships)


def get_table_sample(table_name: str, schema: str = "public", limit: int = 5) -> list[dict[str, Any]]:
    """Get sample rows from a table."""
    with get_readonly_session() as session:
        # Validate table name to prevent injection
        if not table_name.isidentifier():
            return []

        result = session.execute(text(f'SELECT * FROM "{schema}"."{table_name}" LIMIT :limit'),
                                {"limit": limit})
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result]


def get_column_stats(table_name: str, column_name: str, schema: str = "public") -> dict[str, Any]:
    """Get basic statistics for a column."""
    with get_readonly_session() as session:
        # Validate identifiers
        if not table_name.isidentifier() or not column_name.isidentifier():
            return {}

        result = session.execute(text(f"""
            SELECT 
                COUNT(*) as total_count,
                COUNT(DISTINCT "{column_name}") as distinct_count,
                MIN("{column_name}") as min_val,
                MAX("{column_name}") as max_val
            FROM "{schema}"."{table_name}"
        """))
        row = result.first()
        return {
            "total_count": row.total_count,
            "distinct_count": row.distinct_count,
            "min_val": row.min_val,
            "max_val": row.max_val,
        }


def get_schema_summary() -> dict[str, Any]:
    """Get a summary of the database schema for LLM context."""
    schema_info = get_schema_info()

    summary = {
        "total_tables": len(schema_info.tables),
        "tables": {},
    }

    for name, table in schema_info.tables.items():
        summary["tables"][name] = {
            "row_count_estimate": table.row_count,
            "columns": [
                {
                    "name": c.name,
                    "type": c.type,
                    "nullable": c.nullable,
                    "primary_key": c.primary_key,
                    "foreign_key": c.foreign_key,
                }
                for c in table.columns
            ],
            "indexes": table.indexes or [],
        }

    return summary


def get_relevant_schema(question: str, max_tables: int = 10) -> dict[str, Any]:
    """Get schema relevant to a question (simple keyword matching)."""
    # This is a simple implementation - in production, use embeddings/LLM
    question_lower = question.lower()
    schema_info = get_schema_info()

    # Keywords that map to tables
    table_keywords = {
        "users": ["user", "customer", "signup", "registration"],
        "sessions": ["session", "visit", "login"],
        "events": ["event", "action", "click", "view", "purchase"],
        "subscriptions": ["subscription", "plan", "billing", "payment"],
        "payments": ["payment", "revenue", "charge", "invoice"],
        "experiments": ["experiment", "test", "variant", "ab test"],
        "support_tickets": ["ticket", "support", "complaint", "issue"],
        "product_feedback": ["feedback", "review", "nps", "survey"],
    }

    relevant_tables = set()
    for table, keywords in table_keywords.items():
        if any(kw in question_lower for kw in keywords):
            relevant_tables.add(table)

    # Also check for column mentions
    for table_name, table in schema_info.tables.items():
        for col in table.columns:
            if col.name.lower() in question_lower:
                relevant_tables.add(table_name)

    # If no matches, return core tables
    if not relevant_tables:
        relevant_tables = {"users", "events", "sessions", "subscriptions"}

    # Limit tables
    relevant_tables = list(relevant_tables)[:max_tables]

    return {
        name: schema_info.tables[name]
        for name in relevant_tables
        if name in schema_info.tables
    }
