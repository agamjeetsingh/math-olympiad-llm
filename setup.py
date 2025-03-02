from setuptools import setup, find_packages

setup(
    name="o3_at_home",
    version="0.1",
    description="A multi-agent system for LLMs to solve math olympiad problems",
    author="agamjeetsingh",
    packages=find_packages(),
    install_requires=[
        "openai>=1.61.0",
        "python-dotenv>=1.0.0",
        "requests>=2.32.0",
    ],
    python_requires=">=3.8",
)
