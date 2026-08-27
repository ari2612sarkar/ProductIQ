"""
SQL Validator using sqlglot for parsing and safety validation.
Enforces read-only queries, complexity limits, and schema grounding.
"""
import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from config.settings import settings


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    parsed_ast: exp.Expression | None = None
    tables_referenced: set[str] = None
    columns_referenced: set[str] = None
    complexity_score: int = 0


class SQLValidator:
    """Validates SQL queries for safety and correctness."""

    def __init__(self):
        self.forbidden_keywords = set(settings.sql_forbidden_keywords_list)
        self.allowed_schemas = set(settings.sql_allowed_schemas_list)
        self.max_joins = settings.sql_max_joins
        self.max_subqueries = settings.sql_max_subqueries
        self.enable_recursion = settings.sql_enable_recursion

    def validate(self, sql: str) -> ValidationResult:
        """Validate a SQL query."""
        errors = []
        warnings = []
        tables = set()
        columns = set()
        complexity = 0
        parsed = None

        sql_upper = sql.upper()

        # Guardrail for nested SELECT patterns, including malformed SQL.
        inline_subquery_count = len(re.findall(r"\(\s*SELECT\b", sql_upper))
        if inline_subquery_count > self.max_subqueries:
            errors.append(f"Too many subquery expressions: {inline_subquery_count} (max: {self.max_subqueries})")

        # 1. Parse SQL
        try:
            parsed = sqlglot.parse_one(sql, dialect="postgres")
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=errors + [f"SQL parse error: {e!s}"],
                warnings=[],
            )

        # 2. Check for forbidden keywords (case-insensitive)
        for keyword in self.forbidden_keywords:
            keyword_upper = keyword.upper()
            if self._contains_keyword(sql_upper, keyword_upper):
                errors.append(f"Forbidden keyword: {keyword.upper()}")

        # 3. Validate AST for safety
        ast_errors, ast_warnings, ast_tables, ast_columns, ast_complexity = self._validate_ast(parsed)
        errors.extend(ast_errors)
        warnings.extend(ast_warnings)
        tables.update(ast_tables)
        columns.update(ast_columns)
        complexity += ast_complexity

        # 4. Check complexity limits
        if complexity > self.max_joins + self.max_subqueries:
            warnings.append(f"High complexity score: {complexity}")

        # 5. Check table allowlist
        for table in tables:
            schema_table = table.split(".")[-1] if "." in table else table
            if not any(schema_table.startswith(allowed) for allowed in self.allowed_schemas):
                # Only warn, don't error - allow cross-schema queries
                warnings.append(f"Table may be outside allowed schemas: {table}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            parsed_ast=parsed,
            tables_referenced=tables,
            columns_referenced=columns,
            complexity_score=complexity,
        )

    def _contains_keyword(self, sql: str, keyword: str) -> bool:
        """Check if SQL contains keyword as a whole word."""
        # Check for keyword with word boundaries
        pattern = r"\b" + re.escape(keyword) + r"\b"
        return bool(re.search(pattern, sql))

    def _validate_ast(self, ast: exp.Expression) -> tuple[list[str], list[str], set[str], set[str], int]:
        """Walk AST and validate nodes."""
        errors = []
        warnings = []
        tables = set()
        columns = set()
        complexity = 0
        join_count = 0
        subquery_count = 0

        for node in ast.walk():
            # Track tables
            if isinstance(node, exp.Table):
                table_name = node.name
                if node.args.get("db"):
                    table_name = f"{node.args['db']}.{table_name}"
                tables.add(table_name)

            # Track columns
            if isinstance(node, exp.Column):
                col_name = node.name
                if node.args.get("table"):
                    col_name = f"{node.args['table']}.{col_name}"
                columns.add(col_name)

            # Count joins
            if isinstance(node, exp.Join):
                complexity += 1
                join_count += 1

            # Count subqueries
            if isinstance(node, exp.Subquery):
                complexity += 1
                subquery_count += 1

            # Check for recursive CTEs
            if isinstance(node, exp.With) and node.args.get("recursive"):
                if not self.enable_recursion:
                    errors.append("Recursive CTEs are not allowed")

            # Check for dangerous functions
            if isinstance(node, exp.Anonymous) and node.this.upper() in ("PG_SLEEP", "DBLINK", "LO_IMPORT", "LO_EXPORT"):
                errors.append(f"Dangerous function: {node.this.upper()}")

            # Check for system catalog access
            if isinstance(node, exp.Table):
                table_name = node.name.lower()
                if table_name.startswith("pg_") or table_name.startswith("information_schema"):
                    warnings.append(f"System catalog access: {table_name}")

        if join_count > self.max_joins:
            errors.append(f"Too many joins: {join_count} (max: {self.max_joins})")
        if subquery_count > self.max_subqueries:
            errors.append(f"Too many subquery expressions: {subquery_count} (max: {self.max_subqueries})")

        return errors, warnings, tables, columns, complexity

    def get_query_type(self, sql: str) -> str:
        """Determine query type (SELECT, INSERT, etc.)."""
        parsed = sqlglot.parse_one(sql, dialect="postgres")
        if isinstance(parsed, exp.Select):
            return "SELECT"
        if isinstance(parsed, exp.Insert):
            return "INSERT"
        if isinstance(parsed, exp.Update):
            return "UPDATE"
        if isinstance(parsed, exp.Delete):
            return "DELETE"
        if isinstance(parsed, exp.Create):
            return "CREATE"
        if isinstance(parsed, exp.Drop):
            return "DROP"
        return "UNKNOWN"

    def extract_ctes(self, sql: str) -> list[str]:
        """Extract CTE names from query."""
        parsed = sqlglot.parse_one(sql, dialect="postgres")
        ctes = []
        if isinstance(parsed, exp.With):
            for cte in parsed.expressions:
                if isinstance(cte, exp.CTE):
                    ctes.append(cte.alias)
        return ctes

    def estimate_rows(self, sql: str) -> int | None:
        """Rough estimate of rows returned (for SELECT queries)."""
        # This is a placeholder - real implementation would use EXPLAIN
        return None


def validate_sql(sql: str) -> ValidationResult:
    """Convenience function for validating SQL."""
    validator = SQLValidator()
    return validator.validate(sql)
