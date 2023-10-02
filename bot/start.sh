alembic revision -m "next" --autogenerate
alembic upgrade head
python install.py
python run.py