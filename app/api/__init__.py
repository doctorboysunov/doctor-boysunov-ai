"""Run platform services:

  uvicorn app.api.platform_api:app --port 8000   # Medical OS V1 (recommended)
  uvicorn app.api.dashboard_api:app --port 8001  # Legacy dashboard only
  uvicorn app.api.emr_api:app --port 8002        # Legacy EMR only
"""
