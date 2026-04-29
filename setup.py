# setup.py
from setuptools import setup, find_packages

GITHUB = "https://github.com/Laboratory-for-Energy-Systems-Analysis"

setup(
    name='flaskCarculator',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "flaskCarculator": [
            "data/*.yaml",
            "data/*/*.yaml",
            "data/bafu_emission_factors/*.xlsx",
        ],
    },
    python_requires=">=3.11,<3.12",
    install_requires=[
        "Flask",
        "gunicorn",
        "numpy",
        "openpyxl",
        "pandas",
        "PyYAML",
        "scipy",
        "xarray",
        f"carculator_utils @ git+{GITHUB}/carculator_utils.git@e431f50b5117513a82b7aee94d8d0ce9e4062744",
        f"carculator @ git+{GITHUB}/carculator.git@75fd698a0ac3905240b54f0f3475752d97ab7f9c",
        f"carculator_truck @ git+{GITHUB}/carculator_truck.git@fff196e74c733faf1d7c6cdfffaf078ee9c3c008",
        f"carculator_bus @ git+{GITHUB}/carculator_bus.git@24b12888e3414145c2353ce9acb8e1ed0d4a9ccc",
        f"carculator_two_wheeler @ git+{GITHUB}/carculator_two_wheeler.git@52c2157d95597bf9be206949d2dc14a717128b9d",
    ],
    entry_points={
        'console_scripts': [
            'run-app=flaskCarculator:main',
        ],
    },
)
