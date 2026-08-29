from app.services.cribl_client import CriblClient
from app.services.ece_client import ECEClient
from app.services.etn_portal_client import ETNPortalClient

__all__ = [
    "CriblClient",
    "ECEClient",
    "ETNPortalClient",
]

cribl: CriblClient | None = None
ece: ECEClient | None = None
etn_portal: ETNPortalClient | None = None


def init_services(flask_app) -> None:
    """Initialise service client singletons from Flask application config."""
    global cribl, ece, etn_portal

    cribl = CriblClient(
        base_url=flask_app.config.get("CRIBL_SERVICE_URL", "http://localhost:8001"),
    )
    ece = ECEClient(
        base_url=flask_app.config.get("ECE_SERVICE_URL", "http://localhost:8002"),
    )
    etn_portal = ETNPortalClient(
        base_url=flask_app.config.get("ETN_PORTAL_URL", "http://localhost:8080"),
        api_key=flask_app.config.get("ETN_PORTAL_API_KEY"),
    )
