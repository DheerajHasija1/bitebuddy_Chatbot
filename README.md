uv init .
uv add sqlalchemy
uv add langchain langchain-community langchain-groq "groq<1.0" python-dotenv
uv add streamlit
uv pip install psycopg2-binary

uv pip install fastapi uvicorn python-dotenv pyjwt

uv run streamlit run frontend.py
uv run uvicorn bot_api:app --reload --port 8000