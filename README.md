# AgroBridge full stack
Run: python -m venv .venv ; .venv\Scripts\Activate.ps1 ; pip install -r requirements.txt ; uvicorn main:app --reload  -> http://localhost:8000
Deploy: push to GitHub, Render > Web Service > Docker, set env SECRET (long random string). Free tier resets the SQLite file: use Postgres or a disk (DB_PATH) for real use.
Real prices: add data/<crop>.csv (header: month,price; rows like 2024-05,6420) for mustard, wheat, rice, soybean, maize. The model uses it automatically (cached 1 hour).
ML (ml.py): gradient boosting on engineered features, predicting monthly log return; recursive 6-month forecast; walk-forward validation vs a naive baseline; intervals widen with horizon.
   python -m venv .venv
     python -m venv .venv
   pip install -r requirements.txt
   uvicorn main:app --reload