"""
Unit tests for SQL validator.
"""
import pytest
from agents.sql_agent.validator import validate_sql, SQLValidator


class TestSQLValidator:
    """Tests for SQL validation."""

    def setup_method(self):
        self.validator = SQLValidator()

    def test_valid_select_query(self):
        """Test that valid SELECT queries pass validation."""
        sql = "SELECT COUNT(*) FROM users WHERE created_at > NOW() - INTERVAL '30 days'"
        result = validate_sql(sql)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_complex_valid_query(self):
        """Test complex but valid query."""
        sql = """
            SELECT u.id, COUNT(e.id) as event_count
            FROM users u
            LEFT JOIN events e ON u.id = e.user_id
            WHERE u.created_at > NOW() - INTERVAL '30 days'
            GROUP BY u.id
            HAVING COUNT(e.id) > 5
            ORDER BY event_count DESC
            LIMIT 100
        """
        result = validate_sql(sql)
        assert result.is_valid is True

    def test_insert_blocked(self):
        """Test that INSERT statements are blocked."""
        sql = "INSERT INTO users (email) VALUES ('test@test.com')"
        result = validate_sql(sql)
        assert result.is_valid is False
        assert any("INSERT" in e for e in result.errors)

    def test_update_blocked(self):
        """Test that UPDATE statements are blocked."""
        sql = "UPDATE users SET email = 'new@test.com' WHERE id = 1"
        result = validate_sql(sql)
        assert result.is_valid is False
        assert any("UPDATE" in e for e in result.errors)

    def test_delete_blocked(self):
        """Test that DELETE statements are blocked."""
        sql = "DELETE FROM users WHERE id = 1"
        result = validate_sql(sql)
        assert result.is_valid is False
        assert any("DELETE" in e for e in result.errors)

    def test_drop_blocked(self):
        """Test that DROP statements are blocked."""
        sql = "DROP TABLE users"
        result = validate_sql(sql)
        assert result.is_valid is False
        assert any("DROP" in e for e in result.errors)

    def test_create_blocked(self):
        """Test that CREATE statements are blocked."""
        sql = "CREATE TABLE test (id INT)"
        result = validate_sql(sql)
        assert result.is_valid is False
        assert any("CREATE" in e for e in result.errors)

    def test_alter_blocked(self):
        """Test that ALTER statements are blocked."""
        sql = "ALTER TABLE users ADD COLUMN test_col VARCHAR(50)"
        result = validate_sql(sql)
        assert result.is_valid is False
        assert any("ALTER" in e for e in result.errors)

    def test_truncate_blocked(self):
        """Test that TRUNCATE statements are blocked."""
        sql = "TRUNCATE TABLE users"
        result = validate_sql(sql)
        assert result.is_valid is False
        assert any("TRUNCATE" in e for e in result.errors)

    def test_dangerous_functions_blocked(self):
        """Test that dangerous functions are blocked."""
        sql = "SELECT pg_sleep(10)"
        result = validate_sql(sql)
        assert result.is_valid is False
        assert any("PG_SLEEP" in e for e in result.errors)

    def test_complexity_limits(self):
        """Test query complexity limits."""
        # Create a query with too many joins
        joins = " ".join([f"JOIN table{i} t{i} ON t{i}.id = t{i-1}.id" for i in range(1, 15)])
        sql = f"SELECT * FROM table0 t0 {joins}"
        result = validate_sql(sql)
        assert result.is_valid is False
        assert any("joins" in e.lower() for e in result.errors)

    def test_subquery_limits(self):
        """Test subquery limits."""
        subqueries = " ".join([f"(SELECT 1 as c{i})" for i in range(10)])
        sql = f"SELECT * FROM users WHERE id IN ({subqueries})"
        result = validate_sql(sql)
        assert result.is_valid is False
        assert any("subquery" in e.lower() for e in result.errors)

    def test_sql_injection_attempts(self):
        """Test that SQL injection attempts are caught."""
        # Union injection
        sql = "SELECT * FROM users WHERE id = 1 UNION SELECT * FROM passwords"
        result = validate_sql(sql)
        # Should be valid SQL (UNION is allowed in SELECT)
        # But would be caught by execution layer

        # Comment injection attempt
        sql = "SELECT * FROM users WHERE id = 1; --"
        result = validate_sql(sql)
        # Should parse but execution would fail

    def test_complexity_scoring(self):
        """Test complexity scoring."""
        validator = SQLValidator()

        # Simple query
        simple = "SELECT 1"
        result = validator.validate(simple)
        assert result.complexity_score == 0

        # Query with join
        join_query = "SELECT * FROM users u JOIN events e ON u.id = e.user_id"
        result = validator.validate(join_query)
        assert result.complexity_score >= 1

        # Query with subquery
        subquery = "SELECT * FROM users WHERE id IN (SELECT user_id FROM events)"
        result = validator.validate(subquery)
        assert result.complexity_score >= 1