"""Load test configuration"""

import os
from datetime import datetime

# API Configuration
API_HOST = os.getenv("API_HOST", "http://localhost:8000")

# Test User Configuration
TEST_USER_PREFIX = f"loadtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
TEST_PASSWORD = "TestPass123!"

# Test Parameters
DEFAULT_USERS = 10
DEFAULT_SPAWN_RATE = 2
DEFAULT_RUN_TIME = "5m"

# API Endpoints
ENDPOINTS = {
    "register": "/auth/register",
    "login": "/auth/login",
    "list_folders": "/folders",
    "create_folder": "/folders",
    "list_documents": "/documents",
    "upload": "/documents/upload",
    "list_documents_search": "/documents/search",
}
