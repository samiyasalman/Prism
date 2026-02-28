from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://trustbridge:trustbridge_dev@localhost:5432/trustbridge"
    database_url_sync: str = "postgresql://trustbridge:trustbridge_dev@localhost:5432/trustbridge"

    # Auth
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # IBM Watson
    watsonx_api_key: str = ""
    watsonx_project_id: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"

    # IBM Cloud Object Storage
    cos_api_key: str = ""
    cos_instance_id: str = ""
    cos_endpoint: str = "https://s3.us-south.cloud-object-storage.appdomain.cloud"
    cos_bucket: str = "trustbridge-documents"

    # IBM watsonx Orchestrate
    wxo_mcsp_apikey: str = ""
    wxo_instance_url: str = ""
    wxo_agent_id: str = ""

    # RSA keys for credential signing
    rsa_private_key_path: str = "keys/private.pem"
    rsa_public_key_path: str = "keys/public.pem"

    # App
    app_name: str = "Prism"
    frontend_url: str = ""

    model_config = {"env_file": ".env", "env_prefix": "TB_"}


settings = Settings()
