from setuptools import setup, find_packages

setup(
    name="o3_at_home",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "openai>=1.61.0",
        "python-dotenv",
    ],
    python_requires=">=3.8",
)
