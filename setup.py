from setuptools import setup, find_packages

setup(
    name="my_package",  # Name of your package
    version="0.0.0",  # Version of the package
    description="NID Information Extraction",  # Short description

    url="https://github.com/Riaduddin/NID-information-extracts-on-GCP",  # URL to your project repo
    author="Kazi Riad Uddin",  # Author's name
    author_email="rrriaduddin@gmail.com",  # Author's email
    license="MIT",  # License type
    packages=find_packages(),  # Automatically find packages
    install_requires=[],  # Dependencies needed by your package

    python_requires='>=3.6',  # Python version requirement
)
