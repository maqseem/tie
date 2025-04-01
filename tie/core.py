from packaging.version import Version
from typing import Optional, Self
from yaml import SafeLoader
from os import PathLike

TIE_VERSION: str = "0.1.0"

FileDescriptorOrPath = str | int | PathLike

class VersionError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class Tie:
    def __init__(self, path: FileDescriptorOrPath, lc: Optional[str] = None):
        with open(path, "r") as file:
            dom = SafeLoader(file).get_data()
        
        config = dom.get("tie", {})
        dom.pop("tie", None)

        self.dom = dom
        self.default_lc = lc or config.get("default_locale", "en")
        self.locale = lc or self.default_lc
        self.version = config.get("version", TIE_VERSION)
        if Version(self.version) > Version(TIE_VERSION):
            raise VersionError(f"The Tie library version is less than required: {TIE_VERSION} < {self.version}")
    
    def _lc(self, lc: str) -> Self:
        self.lc = lc
        return self
