from packaging.version import Version
from typing import Optional
from typing_extensions import Self
from yaml import SafeLoader, YAMLError
from os import PathLike

from __version__ import VERSION as TIE_VERSION

FileDescriptorOrPath = str | int | PathLike
Primitive = str | int | bool

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
        try:
            with open(path, "r") as file:
                pointer = SafeLoader(file).get_data() or {}
        except FileNotFoundError:
            raise ValueError(f"File not found: {path}")
        except YAMLError:
            raise ValueError(f"Invalid YAML file")

        config = pointer.get("tie", {})
        pointer.pop("tie", None)

        self.pointer = pointer
        self.default_locale = default_locale or config.get("default_locale", "en")
        self.__is_section: bool = True
        self._lc()

        self.version = config.get("version", TIE_VERSION)
        if Version(self.version) > Version(TIE_VERSION):
            raise VersionError(f"The Tie library version is less than required: {TIE_VERSION} < {self.version}")

    def __getattr__(self, attr: str, /) -> Self:
        if not self.__is_section:
            raise AttributeError("The text does not have sections")
        section = self.pointer.get("+" + attr)
        text = self.pointer.get(attr)
        self.__is_section = bool(section)
        self.pointer = section or text
        return self.__copy__()
    
    def __getitem__(self, attr: str, /) -> Self:
        return self.__getattr__(attr)
    
    def __copy__(self):
        node = type(self).__new__(self.__class__)
        node.__dict__.update(self.__dict__)
        return node
    
    def __call__(self, **vars) -> str:
        if isinstance(self.pointer, Primitive):
            return self.pointer
        
        translation = self.pointer.get(self.locale)
        if translation is None:
            raise KeyError(f"Locale '{self.locale}' not found in translations") 
        return translation

    def _lc(self, locale: Optional[str] = None, /) -> Self:
        """
        This function changes the locale.

        Args:
           locale (Optional[str]): the locale being set. If not assigned, the default_locale is used. 

        Returns:
            Self: new Tie instance with assigned locale.
        """
        self.locale = locale or self.default_locale
        return self
