from setuptools import setup

setup(
    version="3.0.0",
    name="dcm-transfer-module",
    description="flask app implementing the DCM Transfer Module API",
    author="LZV.nrw",
    license="MIT",
    python_requires=">=3.10",
    install_requires=[
        "flask==3.*",
        "PyYAML==6.*",
        "data-plumber-http>=1.0.0,<2",
        "dcm-common[services, orchestra]>=4.0.0,<5",
        "dcm-transfer-module-api>=3.0.0,<4",
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
