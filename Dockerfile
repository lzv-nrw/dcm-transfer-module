FROM python:3.10-alpine

# install other
# openssh
RUN apk add openssh
# rsync
RUN apk add rsync

# copy entire directory into container
COPY . /app/dcm-transfer-module
# copy accessories
COPY ./app.py /app/app.py

# set working directory
WORKDIR /app

# install/configure app ..
RUN pip install --upgrade \
    --extra-index-url https://zivgitlab.uni-muenster.de/api/v4/projects/9020/packages/pypi/simple \
    "dcm-transfer-module/[cors]"
RUN rm -r dcm-transfer-module/
ENV ALLOW_CORS=1

# .. and wsgi server (gunicorn)
RUN pip install gunicorn

# define startup
ENTRYPOINT [ "gunicorn" ]
CMD ["--bind", "0.0.0.0:8080", "app:app"]
