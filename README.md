# Digital Curation Manager - Transfer Module

The 'DCM Transfer Module'-API provides functionality to transfer Submission Information Packages (SIPs) from the shared file storage to a remote server.
This repository contains the corresponding Flask app definition.
For the associated OpenAPI-document, please refer to the sibling package [`dcm-transfer-module-api`](https://github.com/lzv-nrw/dcm-transfer-module-api).

The contents of this repository are part of the [`Digital Curation Manager`](https://github.com/lzv-nrw/digital-curation-manager).

## Local install
Make sure to include the extra-index-url `https://zivgitlab.uni-muenster.de/api/v4/projects/9020/packages/pypi/simple` in your [pip-configuration](https://pip.pypa.io/en/stable/cli/pip_install/#finding-packages) to enable an automated install of all dependencies.
Using a virtual environment is recommended.

1. Install with
   ```
   pip install .
   ```
1. Configure service environment to fit your needs ([see here](#environmentconfiguration)).
1. Run app as
   ```
   flask run --port=8080
   ```
1. To manually use the API, either run command line tools like `curl` as, e.g.,
   ```
   curl -X 'POST' \
     'http://localhost:8080/transfer' \
     -H 'accept: application/json' \
     -H 'Content-Type: application/json' \
     -d '{
     "transfer": {
       "target": {
         "path": "jobs/abcde-12345-fghijk-67890"
       }
     }
   }'
   ```
   or run a gui-application, like Swagger UI, based on the OpenAPI-document provided in the sibling package [`dcm-transfer-module-api`](https://github.com/lzv-nrw/dcm-transfer-module-api).

## Run with docker compose
Simply run
```
docker compose up
```
By default, the app listens on port 8080.
The docker volume `file_storage` is automatically created and data will be written in `/file_storage`.
To rebuild an already existing image, run `docker compose build`.

Additionally, a Swagger UI is hosted at
```
http://localhost/docs
```

Additionally, an OpenSSH-server with pre-installed `rsync` is started (listening on port `2222`).
This server is configured for authentication with both username+password (`foo`+`pass`) or via ssh-key (username `foo`).
The corresponding private key is located in `test_dcm_transfer_module/fixtures/.ssh/id_rsa` (it may be required to set file permissions as `chmod 600 test_dcm_transfer_module/fixtures/.ssh/id_rsa` after cloning this repository).
The openssh-server mounts the `test_dcm_transfer_module/remote_storage`-directory to work with (mount source location is chosen due to its use in automated tests).
Test connection via ssh with
```
ssh -i test_dcm_transfer_module/fixtures/.ssh/id_rsa -p 2222 foo@localhost
```
or run `rsync` as
```
rsync -v -e "ssh -i test_dcm_transfer_module/fixtures/.ssh/id_rsa -p 2222" README.md foo@localhost:/remote_storage/README.md
```

Afterwards, stop the process and enter `docker compose down`.

## Tests
Install additional dev-dependencies with
```
pip install -r dev-requirements.txt
```
Run unit-tests with
```
pytest -v -s
```

In order for the full test suite to run, the OpenSSH-server defined in `compose.yml` needs to be available.
Furthermore, the directory `test_dcm_transfer_module/remote_storage` needs to exist and have correct permissions
```
mkdir -m 777 test_dcm_transfer_module/remote_storage
```
The server can be started with
```
docker compose run -i -T -p 2222:2222 openssh-server
```

## Environment/Configuration
Service-specific environment variables are
* `LOCAL_TRANSFER` [DEFAULT 0]: whether to perform only local file transfer
* `SSH_HOSTNAME` [DEFAULT "localhost"]: hostname of the remote machine
* `SSH_PORT` [DEFAULT 22]: port of the ssh-server on remote machine
* `SSH_HOST_PUBLIC_KEY` [DEFAULT None]: public key of the remote machine (requires `SSH_HOST_PUBLIC_KEY_ALGORITHM`)
* `SSH_HOST_PUBLIC_KEY_ALGORITHM` [DEFAULT None]: algorithm for public key of the remote machine (requires `SSH_HOST_PUBLIC_KEY`)
* `SSH_BATCH_MODE` [DEFAULT 1]: whether to use batch mode (disable prompting) for ssh-commands
* `SSH_USERNAME` [DEFAULT "dcm"]: username for ssh-connection to remote machine
* `SSH_IDENTITY_FILE` [DEFAULT "~/.ssh/id_rsa"]: path to private key file for ssh-connection to remote machine
* `SSH_CLIENT_OPTIONS` [DEFAULT []]: JSON array with additional options that are passed to ssh
* `REMOTE_DESTINATION` [DEFAULT "/remote_storage"]: destination directory on remote machine
* `OVERWRITE_EXISTING` [DEFAULT 0]: whether to overwrite existing files on remote machine
* `USE_COMPRESSION` [DEFAULT 0]: whether to use compression for transfer
* `COMPRESSION_LEVEL` [DEFAULT None]: level of compression (see `rsync --compress-level ...`)
* `VALIDATE_CHECKSUMS` [DEFAULT 0]: whether to validate checksums for transferred files
* `TRANSFER_TIMEOUT` [DEFAULT 3]: connection timeout in seconds
* `TRANSFER_RETRIES` [DEFAULT 3]: number of retries for failed transfers
* `TRANSFER_RETRY_INTERVAL` [DEFAULT 360]: interval between retries in seconds
* `TRANSFER_OPTIONS` [DEFAULT []]: JSON array with additional options that are passed to rsync

Additionally this service provides environment options for
* `BaseConfig`,
* `OrchestratedAppConfig`, and
* `FSConfig`

as listed [here](https://github.com/lzv-nrw/dcm-common#app-configuration).

# Contributors
* Sven Haubold
* Orestis Kazasidis
* Stephan Lenartz
* Kayhan Ogan
* Michael Rahier
* Steffen Richters-Finger
* Malte Windrath
* Roman Kudinov