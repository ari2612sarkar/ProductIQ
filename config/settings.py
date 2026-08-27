from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "product-intelligence"
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4

    # Database
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/product_intelligence",
        description="PostgreSQL connection URL",
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout: int = 30
    database_pool_recycle: int = 3600

    # Read-only database for SQL agent (separate credentials)
    database_readonly_url: str | None = None

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_max_connections: int = 50

    # Vector Database
    vector_db_type: str = "pgvector"  # or "qdrant"
    vector_db_url: str = "postgresql://postgres:postgres@localhost:5432/product_intelligence"
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_collection: str = "product_feedback"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    rag_chunk_size: int = 512
    rag_chunk_overlap: int = 50
    rag_top_k: int = 10
    rag_rerank: bool = True
    rag_rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # LLM
    llm_provider: str = "openrouter"  # "openai" or "openrouter"
    llm_model: str = "openrouter/auto"  # Default to auto-selection
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    llm_timeout: int = 60
    llm_max_retries: int = 3
    openai_api_key: str | None = None
    openai_organization: str | None = None
    
    # OpenRouter (OpenAI-compatible API)
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_http_referer: str | None = None
    openrouter_x_title: str | None = None
    
    # Model Selection for Different Tasks
    # Free models available on OpenRouter
    llm_model_sql: str = "openrouter/auto"  # Auto-select best free model for SQL
    llm_model_feedback: str = "openrouter/auto"  # Auto-select for feedback analysis
    llm_model_experiment: str = "openrouter/auto"  # Auto-select for experiments
    llm_model_root_cause: str = "openrouter/auto"  # Auto-select for root cause
    llm_model_decision: str = "openrouter/auto"  # Auto-select for decisions
    llm_model_orchestrator: str = "openrouter/auto"  # Auto-select for orchestrator
    llm_model_general: str = "openrouter/auto"  # Fallback default
    
    # Optional: Force specific free models (uncomment to override)
    # llm_model_sql: str = "meta-llama/llama-3.1-8b-instruct:free"
    # llm_model_feedback: str = "mistralai/mistral-7b-instruct:free"
    # llm_model_experiment: str = "google/gemma-2-9b-it:free"
    # llm_model_root_cause: str = "meta-llama/llama-3.1-8b-instruct:free"
    # llm_model_decision: str = "meta-llama/llama-3.1-8b-instruct:free"
    # llm_model_orchestrator: str = "mistralai/mistral-7b-instruct:free"
    # llm_model_general: str = "google/gemma-2-9b-it:free"

    # SQL Safety
    sql_query_timeout: int = 30
    sql_max_rows: int = 10000
    sql_allowed_schemas: str = "public"
    sql_forbidden_keywords: str = "INSERT,UPDATE,DELETE,DROP,CREATE,ALTER,TRUNCATE,GRANT,REVOKE,COPY,VACUUM,ANALYZE,EXPLAIN ANALYZE,pg_sleep,pg_catalog,information_schema,dblink,lo_"
    sql_max_joins: int = 10
    sql_max_subqueries: int = 5
    sql_enable_recursion: bool = False

    @property
    def sql_allowed_schemas_list(self) -> list[str]:
        return [s.strip() for s in self.sql_allowed_schemas.split(",") if s.strip()]

    @property
    def sql_forbidden_keywords_list(self) -> list[str]:
        return [s.strip() for s in self.sql_forbidden_keywords.split(",") if s.strip()]

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    rate_limit_burst: int = 20

    # API Keys (for protected endpoints)
    api_keys: str = ""

    # Observability
    otel_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "product-intelligence"
    otel_sample_rate: float = 1.0
    prometheus_port: int = 9090
    grafana_url: str = "http://localhost:3000"
    log_format: str = "json"
    log_pii_fields: str = "email,user_id,ip_address,authorization"

    @property
    def api_keys_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def log_pii_fields_list(self) -> list[str]:
        return [s.strip() for s in self.log_pii_fields.split(",") if s.strip()]

    # Data Ingestion
    hf_dataset_name: str = "kevykibbz/ecommerce-behavior-data-from-multi-category-store_oct-nov_2019"
    hf_split: str = "train"
    hf_streaming: bool = True
    hf_batch_size: int = 10000
    upworthy_dataset_url: str = "https://osf.io/jd64p/download"
    data_sample_size: int = 1000000  # Limit for development

    # Agent Configuration
    agent_max_iterations: int = 10
    agent_max_steps: int = 20
    agent_confidence_threshold: float = 0.7
    orchestrator_max_parallel_agents: int = 3

    # Experiment Analysis
    experiment_min_sample_size: int = 100
    experiment_significance_level: float = 0.05
    experiment_multiple_comparison_correction: str = "benjamini-hochberg"

    # Decision Engine
    rice_max_effort: int = 100
    rice_max_reach: int = 1000000
    rice_impact_scale: float = 3.0

    # Evaluation
    evaluation_enabled: bool = True
    evaluation_sample_size: int = 100

    @field_validator("database_readonly_url", mode="before")
    @classmethod
    def set_readonly_url(cls, v: str | None, info) -> str | None:
        if v is None and info.data.get("database_url"):
            # Create read-only URL by adding ?mode=ro or similar
            # For PostgreSQL, we'll use a separate role
            return info.data["database_url"].replace("postgres:postgres", "readonly:readonly")
        return v

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


settings = Settings()
