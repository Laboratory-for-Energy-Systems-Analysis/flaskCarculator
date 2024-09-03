# setup.py
from setuptools import setup, find_packages

setup(
    name='flaskCarculator',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Flask',
        'carculator'
    ],
    entry_points={
        'console_scripts': [
            'run-app=flaskCarculator.__main__:main',
        ],
    },
)
