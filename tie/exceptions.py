class VersionError(Exception):
    """Raised when the version from one source exceeds the version from another."""
    def __init__(self, msg):
        Exception.__init__(self, msg)

class InvalidLocaleError(ValueError):
    """Raised when the given locale does not comply with supported standards."""
    def __init__(self, locale: str):
        super().__init__(f"Locale '{self}' does not comply with supported standards (ISO 639, BCP 47)")
        self.locale = locale
