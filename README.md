# dcm-transfer-module

The 'DCM Transfer Module'-service provides functionality to transfer Submission Information Packages (SIPs) from the shared file storage to a remote server.

## Run locally
Running in a `venv` is recommended.

To test the app locally,
1. install with
   ```
   pip install .
   ```
1. Configure service environment to your needs ([see here](#environmentconfiguration)).
1. run as
   ```
   flask run --port=8080
   ```
1. use either commandline tools like `curl`,
   ```
   curl -X 'POST' \
     'http://localhost:8080/transfer' \
     -H 'accept: application/json' \
     -H 'Content-Type: application/json' \
     -d '{
     "transfer": {
       "target": {
         "path": "file_storage/test_sip"
       }
     }
   }'
   ```
   or a gui like [swagger-ui](https://github.com/lzv-nrw/dcm-transfer-module-api/-/blob/dev/dcm_transfer_module_api/openapi.yaml?ref_type=heads) (see sibling package [`dcm-transfer-module-api`](https://github.com/lzv-nrw/dcm-transfer-module-api)) to submit jobs


## Run with Docker
### Container setup
Use the `compose.yml` to start the `DCM Transfer Module`-container as a service:
```
docker compose up
```
(to rebuild run `docker compose build`).

A Swagger UI is hosted at
```
http://localhost/docs
```
while (by-default) the app listens to port `8080`.

Additionally, an OpenSSH-server with `rsync` available is started listening on port `2222`.
This server is preconfigured for authentication with both username+password (`foo`+`pass`) or via ssh-key (username `foo`).
The corresponding private key is located in `test_dcm_transfer_module/fixtures/.ssh/id_rsa` (it may be required to set file permissions as `chmod 600 test_dcm_transfer_module/fixtures/.ssh/id_rsa` after cloning this repository).
Before starting the server, enter `mkdir -m 777 test_dcm_transfer_module/remote_storage` (or similar) to allow file system access in the configured volume-bind.
User `foo` has full file system permissions in the directory `/remote_storage`.
Connect via ssh with
```
ssh -i test_dcm_transfer_module/fixtures/.ssh/id_rsa -p 2222 foo@localhost
```
or run `rsync` as
```
rsync -v -e "ssh -i test_dcm_transfer_module/fixtures/.ssh/id_rsa -p 2222" README.md foo@localhost:/remote_storage/README.md
```

Afterwards, stop the process for example with `Ctrl`+`C` and enter `docker compose down`.

The build process requires authentication with `zivgitlab.uni-muenster.de` in order to gain access to the required python dependencies.
The Dockerfiles are setup to use the information from `~/.netrc` for this authentication (a gitlab api-token is required).

### File system setup
The currently used docker volume is set up automatically on `docker compose up`. However, in order to move data from the local file system into the container, the container also needs to mount this local file system (along with the volume). To this end, the `compose.yml` needs to be modified before startup with
```
    ...
      - file_storage:/file_storage
      - type: bind
        source: ./test_dcm_transfer_module/fixtures
        target: /local
    ports:
      ...
```
By then opening an interactive session in the container (i.e., after running the compose-script) with
```
docker exec -it <container-id> sh
```
the example IP from the test-related fixtures-directory can be copied over to the volume:
```
cp -r /local/* /file_storage/
```
(The modification to the file `compose.yml` can be reverted after copying.)

## Tests
Install additional dependencies from `dev-requirements.txt`.
Run unit-tests with
```
pytest -v -s --cov dcm_transfer_module
```

In order for the full test suite to run, the OpenSSH-server stub needs to be running.
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

as listed [here](https://github.com/lzv-nrw/dcm-common/-/tree/dev?ref_type=heads#app-configuration).

# Contributors
* Sven Haubold
* Orestis Kazasidis
* Stephan Lenartz
* Kayhan Ogan
* Michael Rahier
* Steffen Richters-Finger
* Malte Windrath
