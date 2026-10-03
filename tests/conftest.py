import os

# Authoritative test isolation defaults:
# Sever all live Gemini API calls and prevent token quota burn during unit test suites.
os.environ.setdefault("UNIT_TEST_MODE", "1")
os.environ.setdefault("MOCK_OFFLINE", "1")
