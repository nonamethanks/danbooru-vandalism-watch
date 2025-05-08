FROM python:3.13-alpine

RUN pip install poetry

WORKDIR /code
COPY danbooru_vandalism_watch /code/danbooru_vandalism_watch
COPY . .

RUN poetry install

ENTRYPOINT [ "poetry", "run", "bot" ]
