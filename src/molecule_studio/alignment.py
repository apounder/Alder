"""Explicit atom correspondence and proper-rotation, unweighted Kabsch RMSD."""
import re
import numpy as np


def rigid_fit(moving, reference):
    moving, reference = np.asarray(moving, dtype=float), np.asarray(reference, dtype=float)
    if (moving.shape != reference.shape or moving.ndim != 2 or moving.shape[1] != 3 or not len(moving)
            or not np.isfinite(moving).all() or not np.isfinite(reference).all()):
        raise ValueError('Alignment needs equally sized, finite coordinate arrays.')
    center, target = moving.mean(axis=0), reference.mean(axis=0)
    u, _, vt = np.linalg.svd((moving - center).T @ (reference - target))
    rotation = u @ np.diag([1, 1, np.linalg.det(u @ vt)]) @ vt
    translation = target - center @ rotation
    fitted = moving @ rotation + translation
    rmsd = float(np.sqrt(np.mean(np.sum((fitted - reference) ** 2, axis=1))))
    return rotation, translation, rmsd


def atom_pairs(reference, moving, heavy=True, mapping=''):
    """Return reference/moving indices; never guess permutations of like elements."""
    if mapping.strip():
        tokens = re.split(r'[\s,;]+', mapping.strip())
        if any(not re.fullmatch(r'\d+:\d+', token) for token in tokens):
            raise ValueError('Use reference:moving atom numbers, e.g. 1:3, 2:1, 3:2 (numbering starts at 1).')
        pairs = np.array([[int(v)-1 for v in token.split(':')] for token in tokens])
        a, b = pairs.T
        if (np.any(a < 0) or np.any(a >= len(reference)) or np.any(b < 0) or np.any(b >= len(moving))
                or len(set(a)) != len(a) or len(set(b)) != len(b)):
            raise ValueError('Atom mapping must use unique, in-range atom numbers.')
    else:
        a = np.flatnonzero(reference != 1) if heavy else np.arange(len(reference))
        b = np.flatnonzero(moving != 1) if heavy else np.arange(len(moving))
    if not len(a) or len(a) != len(b) or not np.array_equal(reference[a], moving[b]):
        raise ValueError('Atom identities/order differ. Enter an explicit mapping of corresponding atoms, or choose a matching subset.')
    return a, b
