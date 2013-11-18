from setuptools import setup, find_packages

setup(
    name="spreadsheet-download-tool",
    version="1.0.0",
    description="",
    long_description=file("README.md").read(),
    author="ScraperWiki",
    author_email="developers@scraperwiki.com",
    url="http://github.com/scraperwiki/spreadsheet-download-tool",
    license="BSD",
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    entry_points={
        "console_scripts": [
            "sdt-create-downloads = create_downloads:main",
        ],
    },
    install_requires=[
        'requests>=1.2.3',
        'cssselect>=0.9.1',
        'xlwt>=0.7.5',
        'autoversion>=1.0.0',
        'unicodecsv>=0.9.4',
        'lxml==3.2.4',
        'scraperwiki==0.3.7',
        'Jinja2==2.7.1', # Including pyexcelerates deps because we include it
    ],
)
