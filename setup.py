from setuptools import setup, find_packages

setup(
    name="tie",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    author="Maqseem",
    description="Ligthweight internationalization library",
    install_requires=["pyyaml", "packaging", "typing_extensions"]
)
