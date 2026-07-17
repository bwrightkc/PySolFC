from pythonforandroid.recipe import PyProjectRecipe
from pythonforandroid.recipes.pyjnius import recipe

# p4a's PyProjectRecipe.build_arch runs `python -m build --wheel` through a
# copy of the target Android python executable. That copy fails to import
# setuptools.build_meta inside pip's isolated PEP 517 build env, which
# breaks pyjnius (a hard Kivy-on-Android dependency) and anything else
# built via PyProjectRecipe/MesonRecipe. --no-isolation runs the build
# against p4a's already-prepared host-python environment instead of
# spinning up a new isolated one; --skip-dependency-check skips a
# preflight check that isn't meaningful under --no-isolation.
#
# This is a class-level default on the shared base class, so patching it
# here (rather than only on a local pyjnius subclass) also covers any
# other PyProjectRecipe-derived recipe this app pulls in, not just this
# one. We still re-export p4a's real, unmodified pyjnius recipe object
# (not a local subclass) so get_recipe_dir() keeps resolving to p4a's own
# recipes/pyjnius/ for its patches -- see ../python3/__init__.py for what
# goes wrong if a local recipe's __file__ doesn't match where its patches
# actually live (that one has to duplicate its patches/ dir because of it).
PyProjectRecipe.extra_build_args = ["--no-isolation", "--skip-dependency-check"]
