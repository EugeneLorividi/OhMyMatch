import os

# Synthetic key for tests only; must be set before app.config is imported.
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-" + "x" * 32)
