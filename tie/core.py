from packaging.version import Version
from typing import Optional
from typing_extensions import Self
from yaml import SafeLoader
from os import PathLike

TIE_VERSION: str = "0.1.0"

FileDescriptorOrPath = str | int | PathLike

class VersionError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class Tie:
    def __init__(self, 
                 path: FileDescriptorOrPath, 
                 default_locale: Optional[str] = None):
        """Initializes a new Tie instance.
        
        Raises:
            VersionError: if the library version is less than specified in yaml file.
        """
        with open(path, "r") as file:
            dom = SafeLoader(file).get_data()
        
        config = dom.get("tie", {})
        dom.pop("tie", None)

        self.dom = dom
        self.default_locale = default_locale or config.get("default_locale", "en")

        self.version = config.get("version", TIE_VERSION)
        if Version(self.version) > Version(TIE_VERSION):
            raise VersionError(f"The Tie library version is less than required: {TIE_VERSION} < {self.version}")

    # def __getattr__(self, attr: str, /) -> Self:
    #     content = self.dom[attr]
    #     if attr.startswith("@"):
    #         self.dom = content
    #     return self

    def _lc(self, locale: Optional[str], /) -> Self:
        """
        This function changes the locale.

        Args:
           locale (Optional[str]): the locale being set. If not assigned, the default_locale is used. 

        Returns:
            Self: new Tie instance with assigned locale.
        """
        self.locale = locale or self.default_locale
        return self

print(Tie("tie.yaml")._lc("en").dom["greeting"]["la"])