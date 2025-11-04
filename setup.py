from setuptools import find_namespace_packages, setup

setup(
    name="aetherlink",
    version="0.1.0",
    packages=find_namespace_packages(include=["pods.*"]),
    install_requires=[
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "pgvector",
        "sentence-transformers",
        "pytest",
    ],
)
