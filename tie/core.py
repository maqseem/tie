from packaging.version import Version
from typing import Iterator, Sequence, IO
from typing_extensions import Self
from yaml import SafeLoader, YAMLError
from pathlib import Path
import inspect
import os
import re

from .__version__ import VERSION as TIE_VERSION
from .exceptions import InvalidLocaleError, VersionError

FileDescriptorOrPath = int | os.PathLike | IO[str] | str
Primitive = str | int | float | bool

ISO_language_code_regex = re.compile("^[a-z]{2,3}(-[a-zA-Z]{2,8})*$")

class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"

class Tie:
    def __init__(self, 
                 path: FileDescriptorOrPath,
                 default_locale: str = "",
                 merge_conflict: str = "",
                 use_fallbacks: bool = True,
                 panic_on_missing: bool = False):
        """
        Initializes a new Tie instance by loading a YAML file.
    
        Args:
            path (FileDescriptorOrPath): The path to the Tie YAML file.
            default_locale (Optional[str]): The default locale used for translations.
            merge_conflict (str): The strategy for merging conflicts (raise, override, or ignore).
            use_fallbacks (bool): Whether to use another locale in the absence of main and default locales.
            panic_on_missing (bool): Whether to raise an exception when no translation is found.

        Raises:
            VersionError: If the required version exceeds the library version.
            FileNotFoundError: If the file cannot be found.
            ValueError: If the YAML file is malformed or the merging conflicts strategy does not exist.
            InvalidLocaleError: If the locale does not comply with supported standards.
        """

        self._merge_conflict: str = merge_conflict

        self._is_section_mode: bool = True
        self._node: dict | Primitive = {}
        self._variables: dict = {}
        self._default_locale: str = default_locale

        self._loaded_files = set()

        if path:
            self.load(path)

    def load(self, *paths: FileDescriptorOrPath) -> None:
        for path in paths:
            if not self._is_section_mode:
                raise TypeError("The file cannot be loaded into the non-section node")
            resolved_path = path
            if isinstance(path, (str, os.PathLike)):
                try:
                    caller_frame = inspect.stack()[-1]
                    caller_dir = Path(os.path.dirname(os.path.abspath(caller_frame.filename)))
                    resolved_path = caller_dir / path
                except (IndexError, ValueError):
                    resolved_path = Path.cwd() / path

            self._load_yaml(resolved_path, target_node=self._node)
        self._extract_variables()

    def _load_yaml(self, path: FileDescriptorOrPath, target_node: dict) -> None:
        if path in self._loaded_files:
            raise ValueError(f"Cyclic import detected: '{path}'")

        content: dict = {}
        try:
            if isinstance(path, int):
                with os.fdopen(path, 'r') as file:
                    content = SafeLoader(file).get_data()
            elif hasattr(path, 'read'):
                content = SafeLoader(file).get_data()
            else:
                with open(path, 'r') as file:
                    content = SafeLoader(file).get_data()

        except FileNotFoundError as e:
            raise FileNotFoundError(f"Tie file not found: {path}") from e
        except YAMLError as e:
            raise ValueError(f"Invalid YAML file") from e

        config = content.get("tie", {})
        content.pop("tie", None)

        self.version = config.get("version", TIE_VERSION)
        if Version(self.version) > Version(TIE_VERSION):
            raise VersionError(f"The required version exceeeds the library version: {self.version} > {TIE_VERSION}")

        parent_section: str = config.get("section")
        if parent_section:
            for section in parent_section.strip().split("."):
                content = {"+" + section: content}

        merge_conflict = self._merge_conflict or config.get("merge_conflict", "override")
        if merge_conflict not in ("raise", "override", "ignore"):
            raise ValueError(
                f"Unknown merge_conflict strategy: '{merge_conflict}'. " 
                f"Expected 'raise', 'override', or 'ignore'")
        self._merge_conflict = merge_conflict

        self._process_node(
            target_node, 
            content, 
            current_path = path)

        self._default_locale: str = self._default_locale or config.get("default_locale", "en-US")
        self.set_locale(inplace=True)

        self._loaded_files.add(path)

    def _process_node(
        self,
        target_node: dict, 
        current_node: dict, 
        current_path: Path
        ) -> None:

        imports = current_node.pop("$import", [])
        if imports and not isinstance(current_path, (str, os.PathLike)):
            raise ValueError(
                f"$import is not supported for file descriptors or streams in '{path}'. "
                f"Use a file path to enable imports"
            )

        elif not (isinstance(imports, list) and all(isinstance(p, str) for p in imports)):
            raise ValueError("Invalid $import format in '{current_path}', expected list of strings")
        
        for import_path in imports:
            parent_path = (current_path if isinstance(current_path, Path) else Path(current_path)).parent

            resolved_path = parent_path / import_path
            if not resolved_path.exists():
                raise FileNotFoundError(f"Imported file not found: '{resolved_path}'") 
            self._load_yaml(resolved_path, current_node)

        for key, value in current_node.items():  
            if isinstance(value, dict):
            # if key in target_node and isinstance(target_node[key], dict) and isinstance(value, dict):
                target_node[key] = target_node.get(key, {})
                self._process_node(target_node[key], value, current_path)
            else:
                if key in target_node and self._merge_conflict == "raise":
                    raise ValueError(f"Merge conflict occured: '{key}'")
                elif key in target_node and self._merge_conflict == "ignore":
                    continue
                target_node[key] = value

    def _extract_variables(self) -> None:
        """Extracts the $variables from the current node to use by default."""
        for subnode, value in self._node.copy().items():
            if str(subnode).startswith("$"):
                self._variables[subnode[1:]] = value
                del self._node[subnode]

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
        if not isinstance(node, dict):
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
        elif isinstance(self._node, Primitive):
            return str(self._node)

        locales = (self._locale, self._default_locale)
        translation = Tie._get_translation(self._node, locales)

        if (wrap := self._node.get("wrap")):
            translation = re.sub(
                "{ *}", "{wrap_text}", wrap
                ).format_map(SafeDict({"wrap_text": translation}))

        for name, value in (lambda d: d.update(vars) or d)(self._variables.copy()).items():
            translation = re.sub(
                "{ *" + name + " *}", 
                str(Tie._get_translation(
                    self._variables[value[1:]] 
                    if isinstance(value, str) and value.startswith("$") 
                    else value, 
                    locales
                )), 
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

    def set_locale(self, locale: str | None = None, inplace: bool = False) -> Self:
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
         
        node = self if inplace else self.__copy__()
        node._locale = locale
        return node

    def render_tree(self, 
                    one_locale_only: bool = False, 
                    **vars: Primitive
                    ) -> dict[str, str | dict]:
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
                clean_key: self[clean_key].render_tree(one_locale_only, **vars)
                for key in self._node
                if (clean_key := key.lstrip("+"))
            }
        elif one_locale_only:
            return self(**vars)
        else:
            return {
                key: str(self.set_locale(key)(**vars))
                for key in self._node if ISO_language_code_regex.match(key)
            }