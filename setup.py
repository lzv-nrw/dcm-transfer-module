from setuptools import setup

setup(
    version="2.1.0",
    name="dcm-transfer-module",
    description="flask app implementing the DCM Transfer Module API",
    author="LZV.nrw",
    license="MIT",
    python_requires=">=3.10",
    install_requires=[
        "flask==3.*",
        "PyYAML==6.*",
        "data-plumber-http>=1.0.0,<2",
        "dcm-common[services, db, orchestration]>=3.25.0,<4",
        "dcm-transfer-module-api>=2.1.0,<3",
    ],
    packages=[
        "dcm_transfer_module",
        "dcm_transfer_module.models",
        "dcm_transfer_module.views",
        "dcm_transfer_module.components"
    ],
    extras_require={
        "cors": ["Flask-CORS==4"],
    },
    setuptools_git_versioning={
          "enabled": True,
          "version_file": "VERSION",
          "count_commits_from_version_file": True,
          "dev_template": "{tag}.dev{ccount}",
    },
)
