from pythonforandroid.recipes.python3 import Python3Recipe


class LocalPython3Recipe(Python3Recipe):
    # NDK r28c's <grp.h> dropped declarations for setgrent/getgrent/
    # endgrent even though bionic still exports them, which turns
    # Modules/grpmodule.c into a hard build failure under
    # -Werror=implicit-function-declaration. See grp-declarations.patch.
    #
    # A local recipe's get_recipe_dir() points here, not at p4a's own
    # recipes/python3/, so Python3Recipe's own patches (paths under
    # patches/) had to be copied into ./patches alongside ours or they'd
    # stop resolving. If buildozer.spec's p4a.commit is ever bumped,
    # re-sync ./patches/ with the new pinned commit's python3 recipe.
    patches = Python3Recipe.patches + ['grp-declarations.patch']


recipe = LocalPython3Recipe()
