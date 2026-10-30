"""Public errors, safe to display without credentials or raw provider responses."""


class GeneratorError(Exception):
    """Base for expected pipeline failures."""


class SpecError(GeneratorError):
    """Malformed or unsupported OpenAPI input."""


class LLMError(GeneratorError):
    """Provider or recorded response failure."""

    def __init__(self, message: str, *, raw_response: str | None = None):
        super().__init__(message)
        self.raw_response = raw_response


class OutputError(GeneratorError):
    """Invalid JSON envelope or contract."""

