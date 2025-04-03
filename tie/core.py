from packaging.version import Version
from typing import Optional
from typing_extensions import Self
from yaml import SafeLoader, YAMLError
from os import PathLike
import re

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
        
        Args:
            path (FileDescriptorOrPath): the path of the Tie YAML file.
            default_locale (Optional[str]): the locale used by default or in the absence of another specified locale.
        Raises:
            VersionError: if the library version is less than specified in yaml file.
            FileNotFoundError: if the file is not found.
            ValueError: if the YAML file is invalid.
        """
        try:
            with open(path, "r") as file:
                pointer = SafeLoader(file).get_data() or {}
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Tie file not found: {path}") from e
        except YAMLError as e:
            raise ValueError(f"Invalid YAML file") from e

        config = pointer.get("tie", {})
        pointer.pop("tie", None)

        self.__pointer = pointer
        self.__default_locale = default_locale or config.get("default_locale", "en")
        self.__is_section: bool = True
        self.set_locale()

        self.version = config.get("version", TIE_VERSION)
        if Version(self.version) > Version(TIE_VERSION):
            raise VersionError(f"The Tie library version is less than required: {TIE_VERSION} < {self.version}")

    def __getattr__(self, attr: str, /) -> Self:
        if not self.__is_section:
            raise AttributeError("The text does not have sections")

        section = self.__pointer.get("+" + attr)
        text = self.__pointer.get(attr)
        self.__is_section = bool(section)

        if not (section or text):
            raise AttributeError(f"'{attr}' as a section or a text not found")

        self.__pointer = section or text
        return self.__copy__()
    
    def __getitem__(self, attr: str, /) -> Self:
        return self.__getattr__(attr)
    
    def __copy__(self):
        node = type(self).__new__(self.__class__)
        node.__dict__.update(self.__dict__)
        return node
    
    def __call__(self, **vars) -> Self | str:
        if isinstance(self.__pointer, Primitive):
            return self.__pointer
        elif self.__is_section:
            raise 

        translation: str = re.sub(" +", " ", 
            self.__pointer.get(self.__locale) or self.__pointer.get(self.__default_locale)
        )
        if translation is None:
            alternative: str = f"or default '{self.__default_locale}' " if self.__default_locale != self.__locale else ""
            raise KeyError(f"Locale '{self.__locale}' {alternative}not found in translations") 

        wrap = self.__pointer.get("wrap")
        if wrap: 
            translation = wrap.replace("{}", translation)
        for name, value in vars.items():
            translation = re.sub("{ *" + name + " *}", str(value), translation)

        return translation

    def __iter__(self):
        if not self.__is_section:
            raise TypeError(f"Iteration is only available for sections")
        for key, value in self.__pointer.items():
            if not key[0] == "+": continue
            yield value

    def __dir__(self) -> list[str]:
        """Returns list of available sections/texts for autocompletion."""
        if not self.__is_section:
            return super().__dir__()

        default_attrs = set(super().__dir__())

        yaml_attrs = set()
        for key in self.__pointer.keys():
            if isinstance(key, str):
                yaml_attrs.add(key[1:] if key.startswith("+") else key)
        return sorted(default_attrs | yaml_attrs) 

    def set_locale(self, locale: Optional[str] = None, /) -> Self:
        """
        Changes the locale.

        Args:
           locale (Optional[str]): the locale being set. If not assigned, a default locale is used. 

        Returns:
            Self: new Tie instance with assigned locale.
        """
        self.__locale = locale or self.__default_locale
        return self

tie = Tie("tie.yaml", "es")