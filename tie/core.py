from collections import defaultdict
from packaging.version import Version
from typing import Iterator, Sequence
from typing_extensions import Self
from yaml import SafeLoader, YAMLError
from os import PathLike
import re

from __version__ import VERSION as TIE_VERSION
from exceptions import InvalidLocaleError, VersionError

FileDescriptorOrPath = str | int | PathLike
Primitive = str | int | float | bool

ISO_language_code_regex = re.compile("^[a-z]{2,3}(-[a-zA-Z]{2,8})*$")

class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"

class Tie:
    def __init__(self, 
                 path: FileDescriptorOrPath, 
                 default_locale: str | None = None):
        """
        Initializes a new Tie instance by loading a YAML file.
    
        Args:
            path (FileDescriptorOrPath): The path to the Tie YAML file.
            default_locale (Optional[str]): The default locale used for translations.

        Raises:
            VersionError: If the required version exceeds the library version.
            FileNotFoundError: If the file cannot be found.
            ValueError: If the YAML file is malformed.
            InvalidLocaleError: If the locale does not comply with supported standards.
        """
        try:
            with open(path, "r") as file:
                content = SafeLoader(file).get_data() or {}
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Tie file not found: {path}") from e
        except YAMLError as e:
            raise ValueError(f"Invalid YAML file") from e

        config = content.get("tie", {})
        content.pop("tie", None)

        self._node: dict = content
        self._is_section_mode: bool = True

        self._default_locale: str = default_locale or config.get("default_locale", "en")
        self.set_locale()

        self._variables: dict = {}
        self._extract_variables()

        self.version = config.get("version", TIE_VERSION)
        if Version(self.version) > Version(TIE_VERSION):
            raise VersionError(f"The required version exceeeds the library version: {self.version} > {TIE_VERSION}")

    def _extract_variables(self) -> None:
        """Extracts the $variables from the current node to use by default."""
        for subnode, value in self._node.items():
            if str(subnode).startswith("$"):
                self._variables[subnode[1:]] = value

    def __getattr__(self, name: str, /) -> Self:
        """
        Navigates to a subnode (section or text) within the current node.

        Args:
            name (str): Name of the subnode. A leading '+' in YAML indicates a section.

        Returns:
            Tie: A Tie node pointing to the selected subnode.

        Raises:
            TypeError: If the current node is not a section and thus has no subnodes.
            AttributeError: If the requested subnode is not found in the current section.
        """
        if not self._is_section_mode:
            raise TypeError("Cannot access the subnode of the non-section node")

        section = self._node.get("+" + name)
        text = self._node.get(name)

        if not (section or text):
            raise AttributeError(f"The requested subnode '{name}' is not found")

        subnode = self.__copy__()
        subnode._is_section_mode = bool(section)
        subnode._node = section or text
        subnode._extract_variables()
        return subnode
    
    def __getitem__(self, name: str, /) -> Self:
        """
        Navigates to a subnode (section or text) within the current node.

        Args:
            name (str): Name of the subnode. A leading '+' in YAML indicates a section.

        Returns:
            Tie: A new Tie node pointing to the selected subnode.

        Raises:
            TypeError: If the current node is not a section and thus has no subnodes.
            AttributeError: If the requested subnode is not found in the current section.
        """
        return self.__getattr__(name)
    
    def __copy__(self) -> Self:
        """
        Creates a shallow copy of the current Tie node.
        
        Returns:
            Tie: A new Tie node with the same parameters and state.
        """
        node = type(self).__new__(self.__class__)
        node.__dict__.update(self.__dict__)
        return node
    
    @staticmethod
    def _get_best_locale_match(requested: str, available: list[str]) -> str | None:
        """
        Finds the best matching locale from the available list based on the requested locale.

        The matching is performed in the following order:
        1. Exact match or fallback to parent locale. (e.g., `zh-Hant-HK` -> `zh-Hant` -> `zh`).
        2. Match a more specific child locale (e.g., `el` -> `el-GR`).
        3. Match any locale with the same base language (e.g., `en-AU` -> `en-CA`).

        Args:
            requested (str): The requested locale.
            available (list[str]): A list of available locale codes.

        Returns:
            str | None: The best matching locale, or None if no match is found.
        """
        requested_parts = requested.lower().split("-")
        available_lower = {x.lower(): x for x in available}
        
        # Exact and parent fallback
        parts = requested_parts[:]
        while parts:
            candidate = "-".join(parts)
            if candidate in available_lower:
                return available_lower[candidate]
            parts.pop()

        # Child fallback
        requested_prefix = requested.lower() + "-"
        for available_code in available_lower: 
            if available_code.startswith(requested_prefix):
                return available_lower[available_code]

        # Same base language
        base = requested_parts[0]
        for available_code in available_lower:
            if available_code.startswith(base + "-"):
                return available_lower[available_code]

        return None

    @staticmethod
    def _get_translation(node: dict | Primitive, locales: Sequence[str]) -> str | None:
        """
        Returns a translation for the highest-priority available locale.

        Args:
            node (dict | Primitive): The text node containing locale-translation pairs or a primitive value.
            locales (Sequence[str]): The sequence of locales ordered by priority.

        Returns:
            str | None: The translation string, None if no options for the requested locales are avaiable.
        
        """

        if isinstance(node, Primitive):
            return node

        for locale in locales:
            if (match := Tie._get_best_locale_match(locale, list(node.keys()))):
                return node.get(match)

    def __call__(self, **vars: dict[str, Primitive]) -> str:
        """
        Renders a translated text for the current locale, formatting it with variables.

        If the current Tie node is a text, this method returns the localized string,
        applying variable substitution (e.g., `{username}` -> `"Maqseem"`).
        If a `wrap` field is present, the final text is wrapped accordingly.

        Returns:
            str: The rendered translation string with subsitued variables.

        Args:
            **vars: Named variables to substitute in the translation string.

        Raises:
            TypeError: If the current node is a section and thus cannot be rendered.
            KeyError: If the current or the default locales are not present.
        """
        if self._is_section_mode:
            raise TypeError("The section cannot be rendered")

        locales = (self._locale, self._default_locale)
        translation = Tie._get_translation(self._node, locales)
        if (wrap := self._node.get("wrap")):
            translation = re.sub(
                "{ *}", "{wrap_text}", wrap
                ).format_map(SafeDict({"wrap_text": translation}))

        for name, value in (lambda d: d.update(vars) or d)(self._variables.copy()).items():
            translation = re.sub(
                "{ *" + name + " *}", 
                str(Tie._get_translation(value, locales)), 
                translation)

        return translation

    def __iter__(self) -> Iterator[Self]:
        """
        Returns an iterator over the text nodes within the current section.

        Returns:
            Iterator[Tie]: The iterator over the text nodes.

        Raise:
            TypeError: If the current node is not a section.
        """
        if not self._is_section_mode:
            raise TypeError(f"The current node is a text and thus cannot be iterated")
        for key in self._node:
            if key.startswith("+") or key.startswith("$"): continue
            yield self[key]

    def __dir__(self) -> list[str]:
        """
        Returns a list of available attributes and methods, 
        including sections and texts for autocompletion.

        Returns:
            list[str]: A list of all available attributes and methods.
        """
        if not self._is_section_mode:
            return super().__dir__()

        default_attrs = set(super().__dir__())
        yaml_attrs = set()
        for key in self._node.keys():
            if isinstance(key, str):
                yaml_attrs.add(key[1:] if key.startswith("+") else key)

        return sorted(default_attrs | yaml_attrs) 

    def set_locale(self, locale: str | None = None, /) -> Self:
        """
        Changes the locale to the specified or the default.

        Args:
           locale (str | None): The locale being set. If not assigned, the default locale is used. 

        Returns:
            Tie: A Tie node with the selected locale.

        Raises:
            InvalidLocaleError: If the locale does not comply with supported standards.
        """
        locale = locale or self._default_locale
        if not ISO_language_code_regex.match(locale):
            raise InvalidLocaleError(locale)
        node = self.__copy__()
        node._locale = locale
        return node

    def render_tree(self, **vars: Primitive) -> dict[str, str | dict]:
        """
        Renders all the texts within every section,
        applying variable substitution (e.g, `"{age}"` -> `17`)
        and resulting into a dictionary.

        Returns:
            dict: A complete structure with rendered texts.
    
        Args:
            **vars: Named variables to substitute in the translation string.
        """
        if self._is_section_mode:
            return {
                clean_key: self[clean_key].render_tree(**vars)
                for key in self._node
                if (clean_key := key.lstrip("+"))
            }
        return {
            key: str(self.set_locale(key)(**vars))
            for key in self._node if ISO_language_code_regex.match(key)
        }