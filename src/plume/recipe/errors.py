"""The error raised for any problem in a recipe; the command line exits with code 2 on it."""


class RecipeError(Exception):
    """A recipe problem, with a message that names the key."""
