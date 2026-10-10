# Core Platform Service Backend

FastAPI backend service powering the Enterprise AI Workspace.

## Quick Setup

1. **Virtual Environment**:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   ```bash
   cp .env.example .env
   ```

4. **Run Server**:
   ```bash
   uvicorn app.main:app --reload --port 8001
   ```

5. **Run Tests**:
   ```bash
   .\.venv\Scripts\pytest.exe -o pythonpath=. tests/test_google_oauth.py
   ```
