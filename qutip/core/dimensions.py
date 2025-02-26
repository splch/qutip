"""
Internal use module for manipulating dims specifications.
"""

# Everything should be explicitly imported, not made available by default.

import numpy as np
from operator import getitem
from functools import partial
from qutip.settings import settings


__all__ = ["to_tensor_rep", "from_tensor_rep", "Space", "Dimensions"]


def flatten(l):
    """Flattens a list of lists to the first level.

    Given a list containing a mix of scalars and lists,
    flattens down to a list of the scalars within the original
    list.

    Examples
    --------

    >>> flatten([[[0], 1], 2]) # doctest: +SKIP
    [0, 1, 2]

    """
    if not isinstance(l, list):
        return [l]
    else:
        return sum(map(flatten, l), [])


def deep_remove(l, *what):
    """Removes scalars from all levels of a nested list.

    Given a list containing a mix of scalars and lists,
    returns a list of the same structure, but where one or
    more scalars have been removed.

    Examples
    --------

    >>> deep_remove([[[[0, 1, 2]], [3, 4], [5], [6, 7]]], 0, 5) # doctest: +SKIP
    [[[[1, 2]], [3, 4], [], [6, 7]]]

    """
    if isinstance(l, list):
        # Make a shallow copy at this level.
        l = l[:]
        for to_remove in what:
            if to_remove in l:
                l.remove(to_remove)
            else:
                l = [deep_remove(elem, to_remove) for elem in l]
    return l


def unflatten(l, idxs):
    """Unflattens a list by a given structure.

    Given a list of scalars and a deep list of indices
    as produced by `flatten`, returns an "unflattened"
    form of the list. This perfectly inverts `flatten`.

    Examples
    --------

    >>> l = [[[10, 20, 30], [40, 50, 60]], [[70, 80, 90], [100, 110, 120]]] # doctest: +SKIP
    >>> idxs = enumerate_flat(l) # doctest: +SKIP
    >>> unflatten(flatten(l), idxs) == l # doctest: +SKIP
    True

    """
    acc = []
    for idx in idxs:
        if isinstance(idx, list):
            acc.append(unflatten(l, idx))
        else:
            acc.append(l[idx])
    return acc


def _enumerate_flat(l, idx=0):
    if not isinstance(l, list):
        # Found a scalar, so return and increment.
        return idx, idx + 1
    else:
        # Found a list, so append all the scalars
        # from it and recurse to keep the increment
        # correct.
        acc = []
        for elem in l:
            labels, idx = _enumerate_flat(elem, idx)
            acc.append(labels)
        return acc, idx


def _collapse_composite_index(dims):
    """
    Given the dimensions specification for a composite index
    (e.g.: [2, 3] for the right index of a ket with dims [[1], [2, 3]]),
    returns a dimensions specification for an index of the same shape,
    but collapsed to a single "leg." In the previous example, [2, 3]
    would collapse to [6].
    """
    return [np.prod(dims)]


def _collapse_dims_to_level(dims, level=1):
    """
    Recursively collapses all indices in a dimensions specification
    appearing at a given level, such that the returned dimensions
    specification does not represent any composite systems.
    """
    if level == 0:
        return _collapse_composite_index(dims)
    return [_collapse_dims_to_level(index, level=level - 1) for index in dims]


def collapse_dims_oper(dims):
    """
    Given the dimensions specifications for a ket-, bra- or oper-type
    Qobj, returns a dimensions specification describing the same shape
    by collapsing all composite systems. For instance, the bra-type
    dimensions specification ``[[2, 3], [1]]`` collapses to
    ``[[6], [1]]``.

    Parameters
    ----------

    dims : list of lists of ints
        Dimensions specifications to be collapsed.

    Returns
    -------

    collapsed_dims : list of lists of ints
        Collapsed dimensions specification describing the same shape
        such that ``len(collapsed_dims[0]) == len(collapsed_dims[1]) == 1``.
    """
    return _collapse_dims_to_level(dims, 1)


def collapse_dims_super(dims):
    """
    Given the dimensions specifications for an operator-ket-, operator-bra- or
    super-type Qobj, returns a dimensions specification describing the same shape
    by collapsing all composite systems. For instance, the super-type
    dimensions specification ``[[[2, 3], [2, 3]], [[2, 3], [2, 3]]]`` collapses to
    ``[[[6], [6]], [[6], [6]]]``.

    Parameters
    ----------

    dims : list of lists of ints
        Dimensions specifications to be collapsed.

    Returns
    -------

    collapsed_dims : list of lists of ints
        Collapsed dimensions specification describing the same shape
        such that ``len(collapsed_dims[i][j]) == 1`` for ``i`` and ``j``
        in ``range(2)``.
    """
    return _collapse_dims_to_level(dims, 2)


def enumerate_flat(l):
    """Labels the indices at which scalars occur in a flattened list.

    Given a list containing a mix of scalars and lists,
    returns a list of the same structure, where each scalar
    has been replaced by an index into the flattened list.

    Examples
    --------

    >>> print(enumerate_flat([[[10], [20, 30]], 40])) # doctest: +SKIP
    [[[0], [1, 2]], 3]

    """
    return _enumerate_flat(l)[0]


def deep_map(fn, collection, over=(tuple, list)):
    if isinstance(collection, over):
        return type(collection)(deep_map(fn, el, over) for el in collection)
    else:
        return fn(collection)


def dims_to_tensor_perm(dims):
    """
    Given the dims of a Qobj instance, returns a list representing
    a permutation from the flattening of that dims specification to
    the corresponding tensor indices.

    Parameters
    ----------

    dims : list, Dimensions
        Dimensions specification for a Qobj.

    Returns
    -------

    perm : list
        A list such that ``data[flatten(dims)[idx]]`` gives the
        index of the tensor ``data`` corresponding to the ``idx``th
        dimension of ``dims``.
    """
    if isinstance(dims, list):
        dims = Dimensions(dims)
    return dims._get_tensor_perm()


def dims_to_tensor_shape(dims):
    """
    Given the dims of a Qobj instance, returns the shape of the
    corresponding tensor. This helps, for instance, resolve the
    column-stacking convention for superoperators.

    Parameters
    ----------

    dims : list, Dimensions
        Dimensions specification for a Qobj.

    Returns
    -------

    tensor_shape : tuple
        NumPy shape of the corresponding tensor.
    """
    perm = dims_to_tensor_perm(dims)
    dims = flatten(dims)
    return tuple(map(partial(getitem, dims), perm))


def dims_idxs_to_tensor_idxs(dims, indices):
    """
    Given the dims of a Qobj instance, and some indices into
    dims, returns the corresponding tensor indices. This helps
    resolve, for instance, that column-stacking for superoperators,
    oper-ket and oper-bra implies that the input and output tensor
    indices are reversed from their order in dims.

    Parameters
    ----------

    dims : list, Dimensions
        Dimensions specification for a Qobj.

    indices : int, list or tuple
        Indices to convert to tensor indices. Can be specified
        as a single index, or as a collection of indices.
        In the latter case, this can be nested arbitrarily
        deep. For instance, [0, [0, (2, 3)]].

    Returns
    -------

    tens_indices : int, list or tuple
        Container of the same structure as indices containing
        the tensor indices for each element of indices.
    """
    perm = dims_to_tensor_perm(dims)
    return deep_map(partial(getitem, perm), indices)


def to_tensor_rep(q_oper):
    """
    Transform a ``Qobj`` to a numpy array whose shape is the flattened
    dimensions.

    ```
    ket.dims == [[2, 3], [1]]
    to_tensor_rep(ket).shape == (2, 3, 1)

    oper.dims == [[2, 3], [2, 3]]
    to_tensor_rep(oper).shape == (2, 3, 2, 3)

    super.dims == [[[2, 3], [2, 3]], [[2, 3], [2, 3]]]
    to_tensor_rep(super).shape == (2, 3, 2, 3, 2, 3, 2, 3)
    ```
    """
    dims = q_oper._dims
    data = q_oper.full().reshape(dims._get_tensor_shape())
    return data.transpose(dims._get_tensor_perm())


def from_tensor_rep(tensorrep, dims):
    """
    Reverse operator of :func:`to_tensor_rep`.
    Create a Qobj From a N-dimensions numpy array and dimensions with N
    indices.
    """
    from . import Qobj
    dims = Dimensions(dims)
    data = tensorrep.transpose(np.argsort(dims._get_tensor_perm()))
    return Qobj(data.reshape(dims.shape), dims=dims)


def _frozen(*args, **kwargs):
    raise RuntimeError("Dimension cannot be modified.")


class MetaSpace(type):
    def __call__(cls, *args, rep=None):
        """
        Select which subclass is instantiated.
        """
        if cls is Space and len(args) == 1 and isinstance(args[0], list):
            # From a list of int.
            return cls.from_list(*args, rep=rep)
        elif len(args) == 1 and isinstance(args[0], Space):
            # Already a Space
            return args[0]

        if cls is Space:
            if len(args) == 0:
                # Empty space: a Field.
                cls = Field
            elif len(args) == 1 and args[0] == 1:
                # Space(1): a Field.
                cls = Field
            elif len(args) == 1 and isinstance(args[0], Dimensions):
                # Making a Space out of a Dimensions object: Super Operator.
                cls = SuperSpace
            elif len(args) > 1 and all(isinstance(arg, Space) for arg in args):
                # list of space: tensor product space.
                cls = Compound

        if settings.core['auto_tidyup_dims']:
            if cls is Compound and all(isinstance(arg, Field) for arg in args):
                cls = Field
            if cls is SuperSpace and args[0].type == "scalar":
                cls = Field

        args = tuple([
            tuple(arg) if isinstance(arg, list) else arg
            for arg in args
        ])

        if cls is Field:
            return cls.field_instance

        if cls is SuperSpace:
            args = (*args, rep or 'super')

        if args not in cls._stored_dims:
            instance = cls.__new__(cls)
            instance.__init__(*args)
            cls._stored_dims[args] = instance
        return cls._stored_dims[args]

    def from_list(cls, list_dims, rep=None):
        if len(list_dims) == 0:
            raise ValueError("Empty list can't be used as dims.")
        elif (
            sum(isinstance(entry, list) for entry in list_dims)
            not in [0, len(list_dims)]
        ):
            raise ValueError(f"Format dims not understood {list_dims}.")
        elif not isinstance(list_dims[0], list):
            # Tensor
            spaces = [Space(size) for size in list_dims]
        elif len(list_dims) == 1:
            # [[2, 3]]: tensor with an extra layer of list.
            spaces = [Space(size) for size in list_dims[0]]
        elif len(list_dims) % 2 == 0:
            # Superoperators or tensor of Superoperators
            spaces = [
                Space(Dimensions(
                    Space(list_dims[i+1]),
                    Space(list_dims[i])
                ), rep=rep)
                for i in range(0, len(list_dims), 2)
            ]
        else:
            raise ValueError(f'Format not understood {list_dims}')

        if len(spaces) == 1:
            return spaces[0]
        elif len(spaces) >= 2:
            return Space(*spaces)
        else:
            raise ValueError(f'Format not understood {list_dims}')


class Space(metaclass=MetaSpace):
    _stored_dims = {}

    def __init__(self, dims):
        idims = int(dims)
        if idims <= 0 or idims != dims:
            raise ValueError("Dimensions must be integers > 0")
        # Size of the hilbert space
        self.size = dims
        self.issuper = False
        # Super representation, should be an empty string except for SuperSpace
        self.superrep = None
        # Does the size and dims match directly: size == prod(dims)
        self._pure_dims = True
        self.__setitem__ = _frozen

    def __eq__(self, other):
        return self is other or (
            type(other) is type(self)
            and other.size == self.size
        )

    def __hash__(self):
        return hash(self.size)

    def __repr__(self):
        return f"Space({self.size})"

    def as_list(self):
        return [self.size]

    def __str__(self):
        return str(self.as_list())

    def dims2idx(self, dims):
        """
        Transform dimensions indices to full array indices.
        """
        return dims

    def idx2dims(self, idx):
        """
        Transform full array indices to dimensions indices.
        """
        return [idx]

    def step(self):
        """
        Get the step in the array between for each dimensions index.

        If element ``[i, j, k]`` is ``ket.full()[m, 0]`` then element
        ``[i, j+1, k]`` is ``ket.full()[m + ket._dims.step()[1], 0]``.
        """
        return [1]

    def flat(self):
        """ Dimensions as a flat list. """
        return [self.size]

    def remove(self, idx):
        """
        Remove a Space from a Dimensons or complex Space.

        ``Space([2, 3, 4]).remove(1) == Space([2, 4])``
        """
        raise RuntimeError("Cannot delete a flat space.")

    def replace(self, idx, new):
        """
        Reshape a Space from a Dimensons or complex Space.

        ``Space([2, 3, 4]).replace(1, 5) == Space([2, 5, 4])``
        """
        if idx != 0:
            raise ValueError(
                "Cannot replace a non-zero index in a flat space."
            )
        return Space(new)

    def replace_superrep(self, super_rep):
        return self


class Field(Space):
    field_instance = None

    def __init__(self):
        self.size = 1
        self.issuper = False
        self.superrep = None
        self._pure_dims = True
        self.__setitem__ = _frozen

    def __eq__(self, other):
        return type(other) is Field

    def __hash__(self):
        return hash(0)

    def __repr__(self):
        return "Field()"

    def as_list(self):
        return [1]

    def step(self):
        return [1]

    def flat(self):
        return [1]

    def remove(self, idx):
        return self

    def replace(self, idx, new):
        return Space(new)


Field.field_instance = Field.__new__(Field)
Field.field_instance.__init__()


class Compound(Space):
    _stored_dims = {}

    def __init__(self, *spaces):
        self.spaces = []
        if len(spaces) <= 1:
            raise ValueError("Compound need multiple space to join.")
        for space in spaces:
            if isinstance(space, Compound):
                self.spaces += space.spaces
            else:
                self.spaces += [space]
        self.spaces = tuple(self.spaces)
        self.size = np.prod([space.size for space in self.spaces])
        self.issuper = all(space.issuper for space in self.spaces)
        if not self.issuper and any(space.issuper for space in self.spaces):
            raise TypeError(
                "Cannot create compound space of super and non super."
            )
        self._pure_dims = all(space._pure_dims for space in self.spaces)
        superrep = [space.superrep for space in self.spaces]
        if all(superrep[0] == rep for rep in superrep):
            self.superrep = superrep[0]
        else:
            raise TypeError(
                "Cannot create compound space of of super operators "
                "with different representation."
            )
        self.__setitem__ = _frozen

    def __eq__(self, other):
        return self is other or (
            type(other) is type(self) and
            self.spaces == other.spaces
        )

    def __hash__(self):
        return hash(self.spaces)

    def __repr__(self):
        parts_rep = ", ".join(repr(space) for space in self.spaces)
        return f"Compound({parts_rep})"

    def as_list(self):
        return sum([space.as_list() for space in self.spaces], [])

    def dims2idx(self, dims):
        if len(dims) != len(self.spaces):
            raise ValueError("Length of supplied dims does not match the number of subspaces.")
        pos = 0
        step = 1
        for space, dim in zip(self.spaces[::-1], dims[::-1]):
            pos += space.dims2idx(dim) * step
            step *= space.size
        return pos

    def idx2dims(self, idx):
        dims = []
        for space in self.spaces[::-1]:
            idx, dim = divmod(idx, space.size)
            dims = space.idx2dims(dim) + dims
        return dims

    def step(self):
        steps = []
        step = 1
        for space in self.spaces[::-1]:
            steps = [step * N for N in space.step()] + steps
            step *= space.size
        return steps

    def flat(self):
        return sum([space.flat() for space in self.spaces], [])

    def remove(self, idx):
        new_spaces = []
        for space in self.spaces:
            n_indices = len(space.flat())
            idx_space = [i for i in idx if i < n_indices]
            idx = [i-n_indices for i in idx if i >= n_indices]
            new_space = space.remove(idx_space)
        if new_spaces:
            return Compound(*new_spaces)
        return Field()

    def replace(self, idx, new):
        new_spaces = []
        for space in self.spaces:
            n_indices = len(space.flat())
            if 0 <= idx < n_indices:
                new_spaces.append(space.replace(idx, new))
            else:
                new_spaces.append(space)
            idx -= n_indices
        return Compound(*new_spaces)

    def replace_superrep(self, super_rep):
        return Compound(
            *[space.replace_superrep(super_rep) for space in self.spaces]
        )


class SuperSpace(Space):
    _stored_dims = {}

    def __init__(self, oper, rep='super'):
        self.oper = oper
        self.superrep = rep
        self.size = oper.shape[0] * oper.shape[1]
        self.issuper = True
        self._pure_dims = oper._pure_dims
        self.__setitem__ = _frozen

    def __eq__(self, other):
        return (
            self is other
            or self.oper == other
            or (
                type(other) is type(self)
                and self.oper == other.oper
                and self.superrep == other.superrep
            )
        )

    def __hash__(self):
        return hash((self.oper, self.superrep))

    def __repr__(self):
        return f"Super({repr(self.oper)}, rep={self.superrep})"

    def as_list(self):
        return self.oper.as_list()

    def dims2idx(self, dims):
        posl, posr = self.oper.dims2idx(dims)
        return posl + posr * self.oper.shape[0]

    def idx2dims(self, idx):
        posl = idx % self.oper.shape[0]
        posr = idx // self.oper.shape[0]
        return self.oper.idx2dims(posl, posr)

    def step(self):
        stepl, stepr = self.oper.step()
        step = self.oper.shape[0]
        return stepl + [step * N for N in stepr]

    def flat(self):
        return sum(self.oper.flat(), [])

    def remove(self, idx):
        new_dims = self.oper.remove(idx)
        if new_dims.type == 'scalar':
            return Field()
        return SuperSpace(new_dims, rep=self.superrep)

    def replace(self, idx, new):
        return SuperSpace(self.oper.replace(idx, new), rep=self.superrep)

    def replace_superrep(self, super_rep):
        return SuperSpace(self.oper, rep=super_rep)


class MetaDims(type):
    def __call__(cls, *args, rep=None):
        if len(args) == 1 and isinstance(args[0], Dimensions):
            return args[0]
        elif len(args) == 1 and len(args[0]) == 2:
            args = (
                Space(args[0][1], rep=rep),
                Space(args[0][0], rep=rep)
            )
        elif len(args) != 2:
            raise NotImplementedError('No Dual, Ket, Bra...', args)
        elif (
            settings.core["auto_tidyup_dims"]
            and args[0] == args[1] == Field()
        ):
            return Field()

        if args not in cls._stored_dims:
            instance = cls.__new__(cls)
            instance.__init__(*args)
            cls._stored_dims[args] = instance
        return cls._stored_dims[args]


class Dimensions(metaclass=MetaDims):
    _stored_dims = {}
    _type = None

    def __init__(self, from_, to_):
        self.from_ = from_
        self.to_ = to_
        self.shape = to_.size, from_.size
        self.issuper = from_.issuper
        self._pure_dims = from_._pure_dims and to_._pure_dims
        self.issquare = False
        if self.from_.size == 1 and self.to_.size == 1:
            self.type = 'scalar'
            self.issquare = True
            self.superrep = None
        elif self.from_.size == 1:
            self.issuper = self.to_.issuper
            self.type = 'operator-ket' if self.issuper else 'ket'
            self.superrep = self.to_.superrep
        elif self.to_.size == 1:
            self.issuper = self.from_.issuper
            self.type = 'operator-bra' if self.issuper else 'bra'
            self.superrep = self.from_.superrep
        elif self.from_ == self.to_:
            self.issuper = self.from_.issuper
            self.type = 'super' if self.issuper else 'oper'
            self.superrep = self.from_.superrep
            self.issquare = True
        else:
            if from_.issuper != to_.issuper:
                raise NotImplementedError(
                    "Operator with both space and superspace dimensions are "
                    "not supported. Please open an issue if you have an use "
                    f"case for these: {from_}, {to_}]"
                )
            self.type = 'super' if self.from_.issuper else 'oper'
            if self.from_.superrep == self.to_.superrep:
                self.superrep = self.from_.superrep
            else:
                self.superrep = 'mixed'
        self.__setitem__ = _frozen

    def __eq__(self, other):
        return (
            self is other
            or (
                type(self) is type(other)
                and self.to_ == other.to_
                and self.from_ == other.from_
            )
        )

    def __hash__(self):
        return hash((self.to_, self.from_))

    def __repr__(self):
        return f"Dimensions({repr(self.from_)}, {repr(self.to_)})"

    def __str__(self):
        return str(self.as_list())

    def as_list(self):
        """
        Return the list representation of the Dimensions object.
        """
        return [self.to_.as_list(), self.from_.as_list()]

    def __getitem__(self, key):
        if key == 0:
            return self.to_
        elif key == 1:
            return self.from_
        raise IndexError("Dimensions index out of range")

    def dims2idx(self, dims):
        """
        Transform dimensions indices to full array indices.
        """
        return self.to_.dims2idx(dims[0]), self.from_.dims2idx(dims[1])

    def idx2dims(self, idxl, idxr):
        """
        Transform full array indices to dimensions indices.
        """
        return [self.to_.idx2dims(idxl), self.from_.idx2dims(idxr)]

    def step(self):
        """
        Get the step in the array between for each dimensions index.

        If element ``[i, j, k]`` is ``ket.full()[m, 0]`` then element
        ``[i, j+1, k]`` is ``ket.full()[m + ket._dims.step()[1], 0]``.
        """
        return [self.to_.step(), self.from_.step()]

    def flat(self):
        """ Dimensions as a flat list. """
        return [self.to_.flat(), self.from_.flat()]

    def _get_tensor_shape(self):
        """
        Get the shape to of the Nd tensor with one dimensions for each
        Dimension index. The order of the space values are not in the order of
        the Dimension index.
        """
        # dims_to_tensor_shape
        stepl = self.to_.step()
        flatl = self.to_.flat()
        stepr = self.from_.step()
        flatr = self.from_.flat()
        return tuple(np.concatenate([
            np.array(flatl)[np.argsort(stepl)[::-1]],
            np.array(flatr)[np.argsort(stepr)[::-1]],
        ]))

    def _get_tensor_perm(self):
        """
        Get the permutation of a tensor created using ``_get_tensor_shape`` to
        reorder the tensor dimensions with those of the Dimensions object.
        """
        # dims_to_tensor_perm
        stepl = self.to_.step()
        stepr = self.from_.step()
        return list(np.concatenate([
            np.argsort(stepl)[::-1],
            np.argsort(stepr)[::-1] + len(stepl)
        ]))

    def remove(self, idx):
        """
        Remove a Space from a Dimensons or complex Space.

        ``Space([2, 3, 4]).remove(1) == Space([2, 4])``
        """
        if not isinstance(idx, list):
            idx = [idx]
        if not idx:
            return self
        idx = sorted(idx)
        n_indices = len(self.to_.flat())
        idx_to = [i for i in idx if i < n_indices]
        idx_from = [i-n_indices for i in idx if i >= n_indices]
        return Dimensions(
            self.from_.remove(idx_from),
            self.to_.remove(idx_to),
        )

    def replace(self, idx, new):
        """
        Reshape a Space from a Dimensons or complex Space.

        ``Space([2, 3, 4]).replace(1, 5) == Space([2, 5, 4])``
        """
        n_indices = len(self.to_.flat())
        if idx < n_indices:
            new_to = self.to_.replace(idx, new)
            new_from = self.from_
        else:
            new_to = self.to_
            new_from = self.from_.replace(idx-n_indices, new)

        return Dimensions(new_from, new_to)

    def replace_superrep(self, super_rep):
        if not self.issuper and super_rep is not None:
            raise TypeError("Can't set a superrep of a non super object.")
        return Dimensions(
            self.from_.replace_superrep(super_rep),
            self.to_.replace_superrep(super_rep)
        )
