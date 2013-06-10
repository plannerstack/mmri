from setuptools import setup, find_packages

setup(
    name = 'mmri',
    version = '0.1.0-dev',
    author = 'Go About and others',
    author_email = 'tech@goabout.com',
    license = 'MIT',
    description = 'Source code for the Beter Benutten MMRI project',
    long_description = open('README.rst').read(),
    url = 'http://github.com/goabout/mmri',
    download_url = 'http://github.com/goabout/mmri/archives/master',
    packages = find_packages(),
    include_package_data = True,
    zip_safe = False,
    platforms = ['all'],
    entry_points = {
        'console_scripts': [
            'test-otp = mmri.test_otp:main',
        ],
    },
    install_requires = [
        'requests',
    ],
)
