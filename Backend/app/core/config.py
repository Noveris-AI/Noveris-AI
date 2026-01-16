"""
Configuration management using Pydantic Settings.

All configuration values are loaded from environment variables
with sensible defaults where appropriate.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the Backend directory (where the .env file is located)
# Backend is at: /path/to/Noveris-AI/Backend/app/core/config.py
# Backend dir is: /path/to/Noveris-AI/Backend/
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"

# Load .env into environment for nested settings models
from dotenv import load_dotenv
load_dotenv(ENV_FILE)


class AppSettings(BaseSettings):
    """Application-level configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "noveris-ai"
    app_version: str = "1.0.0"
    app_debug: bool = False
    app_tz: str = "UTC"

    # Frontend
    frontend_base_url: str = "http://0.0.0.0:3000"
    sso_success_redirect_path: str = "/dashboard"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    api_limit_concurrency: int = 1000
    api_timeout_keep_alive: int = 5

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:8080"
    cors_credentials: bool = True

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="DB_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    host: str = "localhost"
    port: int = 5432
    name: str = "noveris_db"
    user: str = "noveris_user"
    password: str = ""
    pool_size: int = 20
    max_overflow: int = 10
    connect_timeout: int = 30
    auto_migrate: bool = True

    @property
    def dsn(self) -> str:
        """Get async database DSN."""
        auth_part = f"{self.user}:{self.password}@" if self.password else f"{self.user}@"
        return f"postgresql+asyncpg://{auth_part}{self.host}:{self.port}/{self.name}"

    @property
    def sync_dsn(self) -> str:
        """Get synchronous database DSN for Alembic."""
        auth_part = f"{self.user}:{self.password}@" if self.password else f"{self.user}@"
        return f"postgresql://{auth_part}{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="REDIS_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = True
    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0
    pool_size: int = 50
    session_prefix: str = "session:"
    ratelimit_prefix: str = "ratelimit:"
    verify_prefix: str = "verify:"

    @property
    def dsn(self) -> str:
        """Get Redis DSN."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class SecuritySettings(BaseSettings):
    """Security configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    secret_key: str = Field(default="", min_length=32)
    password_hash_rounds: int = Field(default=12, ge=4, le=31)

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key is set in production."""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v


class SessionSettings(BaseSettings):
    """Session configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="SESSION_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    cookie_name: str = "session_id"
    cookie_domain: str = ""
    cookie_secure: bool = False
    cookie_httponly: bool = True
    cookie_samesite: Literal["strict", "lax", "none"] = "lax"
    ttl: int = 86400  # 1 day
    remember_ttl: int = 2592000  # 30 days
    max_sessions_per_user: int = 5
    extend_on_activity: bool = True


class CsrfSettings(BaseSettings):
    """CSRF protection configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="CSRF_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = True
    cookie_name: str = "csrf_token"
    cookie_domain: str = ""
    cookie_secure: bool = False
    cookie_httponly: bool = False
    cookie_samesite: Literal["strict", "lax", "none"] = "strict"
    token_length: int = 32
    header_name: str = "X-CSRF-Token"


class PasswordSettings(BaseSettings):
    """Password policy configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="PASSWORD_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    min_length: int = Field(default=8, ge=6, le=128)
    max_length: int = Field(default=128, ge=6, le=256)
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digit: bool = True
    require_special: bool = True
    special_chars: str = "!@#$%^&*()_+-=[]{}|;:,.<>?"


class RateLimitSettings(BaseSettings):
    """Rate limiting configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="RATE_LIMIT_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = True
    default: int = 100
    window: int = 60
    login_attempts: int = 5
    login_window: int = 300
    code_requests: int = 10
    code_window: int = 3600
    ban_duration: int = 3600


class VerifySettings(BaseSettings):
    """Verification and reset token configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    verify_code_length: int = Field(default=6, ge=4, le=8)
    verify_code_ttl: int = 600  # 10 minutes
    reset_token_ttl: int = 3600  # 1 hour
    reset_mode: Literal["token", "code", "both"] = "token"
    register_require_code: bool = False
    verify_dev_log_code: bool = True


class SmtpSettings(BaseSettings):
    """SMTP/email configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="SMTP_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = False
    host: str = "localhost"
    port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = "noreply@noveris.ai"
    from_name: str = "Noveris AI"
    use_tls: bool = True
    template_dir: str = "./templates/email"


class SsoSettings(BaseSettings):
    """SSO configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="SSO_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    oidc_providers: str = ""
    oauth2_providers: str = ""
    saml_providers: str = ""


class MinioSettings(BaseSettings):
    """MinIO object storage configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="MINIO_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = False
    endpoint: str = "localhost:9000"
    access_key: str = ""
    secret_key: str = ""
    bucket: str = "noveris"
    secure: bool = False


class ElasticsearchSettings(BaseSettings):
    """Elasticsearch configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="ES_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = False
    dsn: str = "http://localhost:9200"
    index_prefix: str = "noveris"


class LogSettings(BaseSettings):
    """Logging configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="LOG_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    level: str = "INFO"
    format: Literal["json", "text"] = "json"
    path: str = ""
    requests: bool = True
    sanitize: bool = True


class AnsibleSettings(BaseSettings):
    """Ansible configuration for Node Management."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="ANSIBLE_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    work_dir: str = "/tmp/noveris_ansible"
    forks: int = 50
    timeout: int = 300
    ssh_args_default: str = "-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null"
    become_method: Literal["sudo", "su", "pbrun", "pfexec", "doas", "dzdo", "ksu"] = "sudo"
    gather_facts: bool = True
    collections_paths: str = "/usr/share/ansible/collections:/usr/local/share/ansible/collections:~/.ansible/collections"
    roles_path: str = "/usr/share/ansible/roles:/usr/local/share/ansible/roles:~/.ansible/roles"
    playbook_repo_path: str = "./app/ansible/playbooks"
    host_key_checking: bool = False
    private_key_file: str = ""


class JobRunnerSettings(BaseSettings):
    """Job Runner configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="RUNNER_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    concurrency: int = 10
    queue_name: str = "ansible_jobs"
    result_ttl: int = 86400  # 24 hours
    cancel_grace_period: int = 10
    heartbeat_interval: int = 30
    log_retention_days: int = 30


class NodeManagementSettings(BaseSettings):
    """Node Management configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="NODE_MGMT_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = True
    local_node_auto_register: bool = True
    connectivity_check_interval: int = 300  # 5 minutes
    fact_collection_interval: int = 3600  # 1 hour
    max_concurrent_per_node: int = 1
    default_ssh_port: int = 22
    default_connection_timeout: int = 30
    serial_batch_size: int = 10  # Percentage for rolling updates
    artifacts_bucket: str = "noveris-job-artifacts"


class CredentialSettings(BaseSettings):
    """Credential encryption configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="CREDENTIAL_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    master_key: str = Field(default="", min_length=32)
    key_version: int = 1
    algorithm: Literal["AES256_GCM", "AES256_CBC"] = "AES256_GCM"
    kms_enabled: bool = False
    kms_key_id: str = ""

    @field_validator("master_key")
    @classmethod
    def validate_master_key(cls, v: str) -> str:
        """Validate master key is set in production."""
        import os
        if os.getenv("APP_ENV") == "production" and len(v) < 32:
            raise ValueError("CREDENTIAL_MASTER_KEY must be at least 32 characters long in production")
        return v or "dev-master-key-change-in-production-32chars"


class DeploymentSettings(BaseSettings):
    """Model Deployment configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="DEPLOY_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service configuration
    default_host: str = "0.0.0.0"
    port_range_start: int = 20000
    port_range_end: int = 40000

    # Directories on target nodes
    systemd_service_dir: str = "/etc/systemd/system"
    venv_base: str = "/opt/model-runtimes"
    user: str = "modelserve"
    work_dir: str = "/var/lib/model-deployments"

    # Model cache configuration
    model_cache_root: str = "/data/models"
    log_root: str = "/data/logs/models"

    # Hugging Face configuration
    hf_token: str = ""
    hf_endpoint: str = ""  # e.g., https://hf-mirror.com for China
    hf_home: str = ""  # Defaults to MODEL_CACHE_ROOT/huggingface
    hf_hub_enable_hf_transfer: bool = False
    hf_xet_high_performance: bool = False

    # Timeouts and retries
    download_timeout: int = 3600  # 1 hour for model downloads
    install_timeout: int = 1800  # 30 minutes for framework installation
    health_check_timeout: int = 30
    health_check_interval: int = 60
    max_retries: int = 3

    # Observability
    enable_metrics: bool = True
    enable_health_check: bool = True

    @property
    def hf_home_path(self) -> str:
        """Get HF_HOME path, defaulting to model_cache_root/huggingface."""
        return self.hf_home or f"{self.model_cache_root}/huggingface"


class ChatSettings(BaseSettings):
    """Chat/Playground module configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="CHAT_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Feature toggles
    enabled: bool = True
    public_enabled: bool = True

    # Public chat base URL (for generating shareable links)
    public_base_url: str = ""

    # Web search toggle (global kill switch)
    enable_web_search: bool = False

    # File upload settings
    upload_max_file_size_mb: int = 50
    upload_allowed_extensions: str = ".txt,.md,.pdf,.doc,.docx,.xls,.xlsx,.csv,.json,.xml,.html,.py,.js,.ts,.java,.c,.cpp,.go,.rs,.yaml,.yml,.png,.jpg,.jpeg,.gif,.webp,.mp3,.wav,.ogg,.mp4,.webm"
    upload_max_files_per_message: int = 10

    # Document processing
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_chunks_per_document: int = 1000

    # Embedding settings
    default_embedding_model: str = ""
    embedding_batch_size: int = 100

    # Retrieval settings
    retrieval_top_k: int = 5
    retrieval_score_threshold: float = 0.7

    # Streaming settings
    stream_timeout_ms: int = 120000
    stream_chunk_size: int = 1024

    # Rate limiting for chat
    rate_limit_messages_per_minute: int = 20
    rate_limit_messages_per_day: int = 1000

    # Conversation limits
    max_messages_per_conversation: int = 500
    max_conversations_per_user: int = 100
    conversation_title_max_length: int = 200

    # MinIO bucket for chat attachments
    attachments_bucket: str = "chat-attachments"

    @property
    def allowed_extensions_list(self) -> list[str]:
        """Parse allowed extensions into a list."""
        return [ext.strip().lower() for ext in self.upload_allowed_extensions.split(",")]


class MCPSettings(BaseSettings):
    """MCP (Model Context Protocol) configuration."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_prefix="MCP_",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Global MCP enable/disable
    enabled: bool = True

    # Web search MCP server
    web_search_enabled: bool = False
    web_search_server_url: str = ""
    web_search_searxng_url: str = "http://localhost:8888"
    web_search_results_limit: int = 10
    web_search_timeout_ms: int = 30000

    # Docs MCP server
    docs_server_enabled: bool = True
    docs_server_url: str = ""

    # Tool call auditing
    audit_tool_calls: bool = True
    audit_redact_arguments: bool = False
    audit_max_result_size: int = 10000

    # Rate limiting for MCP calls
    rate_limit_calls_per_minute: int = 60

    # Allowed MCP server hosts (security)
    # Format: "localhost,127.0.0.1,internal.company.com"
    allowed_server_hosts: str = "localhost,127.0.0.1"

    @property
    def allowed_hosts_list(self) -> list[str]:
        """Parse allowed hosts into a list."""
        return [host.strip() for host in self.allowed_server_hosts.split(",")]


class Settings(BaseSettings):
    """Main settings class that aggregates all configuration sections."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    csrf: CsrfSettings = Field(default_factory=CsrfSettings)
    password: PasswordSettings = Field(default_factory=PasswordSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    verify: VerifySettings = Field(default_factory=VerifySettings)
    smtp: SmtpSettings = Field(default_factory=SmtpSettings)
    sso: SsoSettings = Field(default_factory=SsoSettings)
    minio: MinioSettings = Field(default_factory=MinioSettings)
    elasticsearch: ElasticsearchSettings = Field(default_factory=ElasticsearchSettings)
    log: LogSettings = Field(default_factory=LogSettings)
    ansible: AnsibleSettings = Field(default_factory=AnsibleSettings)
    job_runner: JobRunnerSettings = Field(default_factory=JobRunnerSettings)
    node_management: NodeManagementSettings = Field(default_factory=NodeManagementSettings)
    credential: CredentialSettings = Field(default_factory=CredentialSettings)
    deployment: DeploymentSettings = Field(default_factory=DeploymentSettings)
    chat: ChatSettings = Field(default_factory=ChatSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)

    # DOCS
    docs_enabled: bool = True
    dev_auto_reload: bool = True


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
