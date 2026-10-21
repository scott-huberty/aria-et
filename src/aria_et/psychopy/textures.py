"""Explicit cleanup for disposable PsychoPy image stimuli."""

from __future__ import annotations


# WORKAROUND for PsychoPy's cross-thread GL cleanup bug (psychopy#7844):
# ImageStim.__del__ frees textures on whichever thread runs garbage collection,
# which can have no OpenGL context (access violation 0x...A38 in session.log).
# Fixed upstream in 0036aa96, expected in 2027.1.0, not in 2026.2.5.
# Remove this helper and its calls once pyproject.toml requires PsychoPy >=
# 2027.1.0 (verify that release includes #7844).
# See issues/psychopy-imagestim-gldeletetextures.md.
def clear_image_textures(image: object) -> None:
    """Release a trial's image on the presentation thread with its GL context.

    PsychoPy 2026.2.1's clearTextures does not remove the texture/buffer IDs.
    Remove them here so a later destructor cannot delete a reused GL name.
    Retire the IDs even if native cleanup fails partway; propagate that error
    rather than attempting unsafe cleanup again during garbage collection.
    Injected draw-only stimuli have no native textures and need no cleanup.
    """
    clear_textures = getattr(image, "clearTextures", None)
    if clear_textures is None:
        return
    try:
        clear_textures()
    finally:
        for attribute in ("_texID", "_maskID", "_pixBuffID"):
            if hasattr(image, attribute):
                delattr(image, attribute)
