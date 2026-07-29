from setuptools import Distribution, setup


class BinaryDistribution(Distribution):
    """Tag the tester wheel for its CPython/platform-specific native bridge."""

    def has_ext_modules(self) -> bool:
        return True


setup(distclass=BinaryDistribution)
