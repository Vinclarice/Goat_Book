FROM python:3.14-slim

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

RUN pip install "django<6" gunicorn whitenoise

COPY src /src

WORKDIR /src

CMD ["gunicorn", "--bind", "0.0.0.0:8888", "superlists.wsgi:application"]

