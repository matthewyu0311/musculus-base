import operator
from collections.abc import Callable, Iterable, MutableSequence, Sequence
from functools import partial
from itertools import repeat
from math import fma, sqrt
from typing import Literal, cast, overload

from .number import FracOrFloat, frac

type Tuple1 = tuple[FracOrFloat]
type Tuple3 = tuple[FracOrFloat, FracOrFloat, FracOrFloat]
type Tuple4 = tuple[FracOrFloat, FracOrFloat, FracOrFloat, FracOrFloat]
################################################
# Simple matrix operations without numpy
################################################
type MatrixRow_N = tuple[FracOrFloat, ...]
type MatrixRow_1 = tuple[FracOrFloat]
type MatrixRow_2 = tuple[FracOrFloat, FracOrFloat]
type MatrixRow_3 = Tuple3


type Matrix_M[N: MatrixRow_N = MatrixRow_N] = tuple[N, ...]
type Matrix_Mx1 = tuple[MatrixRow_1, ...]

# 3x3 matrices are very common
type Matrix_1xN[N: MatrixRow_N] = tuple[N]
type Matrix_2xN[N: MatrixRow_N] = tuple[N, N]
type Matrix_3xN[N: MatrixRow_N] = tuple[N, N, N]

type Matrix_1x2 = Matrix_1xN[MatrixRow_2]
type Matrix_1x3 = Matrix_1xN[MatrixRow_3]
type Matrix_2x1 = Matrix_2xN[MatrixRow_1]
type Matrix_2x2 = Matrix_2xN[MatrixRow_2]
type Matrix_2x3 = Matrix_2xN[MatrixRow_3]
type Matrix_3x1 = Matrix_3xN[MatrixRow_1]
type Matrix_3x2 = Matrix_3xN[MatrixRow_2]
type Matrix_3x3 = Matrix_3xN[MatrixRow_3]

type MutableMatrix = list[list[FracOrFloat]]
type AnyMatrix = Matrix_M | MutableMatrix


def matrix_size(matrix: AnyMatrix, /) -> tuple[int, int]:
    """Return `m` and `n` of `m x n` matrix."""
    # O(1)
    return len(matrix), len(matrix[0])


# To replace a value in a mutable matrix,
# one can simply do mutable_matrix[m][n] = foo
# NOTE: unlike mathematical matrices, these ones have zero-based indices!


@overload
def matrix_copy(
    matrix: MutableMatrix, /, *, mutable: Literal[False] = False
) -> Matrix_M: ...


@overload
def matrix_copy[M: Matrix_M](matrix: M, /, *, mutable: Literal[False] = False) -> M: ...


@overload
def matrix_copy(matrix: AnyMatrix, /, *, mutable: Literal[True]) -> MutableMatrix: ...


def matrix_copy(matrix: AnyMatrix, /, *, mutable: bool = False):
    # O(m*n)
    fn = list if mutable else tuple
    return fn(fn(row) for row in matrix)


@overload
def matrix_from(
    m: Literal[3],
    n: Literal[3],
    values: Iterable[FracOrFloat],
    *,
    mutable: Literal[False] = False,
) -> Matrix_3x3: ...


@overload
def matrix_from(
    m: int, n: int, values: Iterable[FracOrFloat], *, mutable: Literal[False] = False
) -> Matrix_M: ...


@overload
def matrix_from(
    m: int, n: int, values: Iterable[FracOrFloat], *, mutable: Literal[True]
) -> MutableMatrix: ...


def matrix_from(m, n, values, *, mutable=False):
    """NOTE: This function only consumes the required number of elements in the iterator."""
    fn = list if mutable else tuple
    elements = fn(item for _, item in zip(range(m * n), iter(values), strict=False))
    if len(elements) != m * n:
        raise IndexError(f"Expected {m} x {n} elements, got {len(elements)} elements")
    return fn(elements[a : a + n] for a in range(0, m * n, n))


@overload
def matrix_fill(
    m: int, n: int, value: FracOrFloat = 0, *, mutable: Literal[False] = False
) -> Matrix_M: ...


@overload
def matrix_fill(
    m: int, n: int, value: FracOrFloat = 0, *, mutable: Literal[True]
) -> MutableMatrix: ...


def matrix_fill(m: int, n: int, value: FracOrFloat = 0, *, mutable: bool = False):
    # O(m)
    fn = list if mutable else tuple
    return fn(fn(repeat(value, n)) for _ in range(m))


def matrix_values(matrix: AnyMatrix, /) -> Iterable[FracOrFloat]:
    # O(m*n)
    return (item for row in matrix for item in row)


def matrix_column(matrix: AnyMatrix, /, j: int) -> Matrix_Mx1:
    # O(m)
    return tuple((row[j],) for row in matrix)


def matrix_column_values(matrix: AnyMatrix, /, j: int) -> Sequence[FracOrFloat]:
    # O(m)
    return tuple(row[j] for row in matrix)


def matrix_column_vector(*values: FracOrFloat) -> Matrix_Mx1:
    return tuple((v,) for v in values)


def matrix_row_vector(*values: FracOrFloat) -> Matrix_1xN:
    return (values,)


MATRIX_IDENTITY_2x2: Matrix_2x2 = ((1, 0), (0, 1))
MATRIX_IDENTITY_3x3: Matrix_3x3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def matrix_identity(m: int, *, mutable: bool = False) -> AnyMatrix:
    fn = list if mutable else tuple
    return fn(fn(1 if j == i else 0 for j in range(m)) for i in range(m))


def matrix_transpose(matrix: AnyMatrix, /) -> MutableMatrix:
    m, n = matrix_size(matrix)
    # O(n)
    output = matrix_fill(n, m, mutable=True)
    # O(m*n)
    for i in range(m):
        for j in range(n):
            output[j][i] = matrix[i][j]
    return output


def matrix_aggregate(
    op: Callable[[Sequence[FracOrFloat]], FracOrFloat],
    matrix: AnyMatrix,
    /,
    *matrices: AnyMatrix,
    mutable=False,
) -> AnyMatrix:
    fn = list if mutable else tuple
    return fn(
        fn(op(items) for items in zip(*rows, strict=True))
        for rows in zip(matrix, *matrices, strict=True)
    )


matrix_add = partial(matrix_aggregate, sum)


@overload
def matrix_unary(
    op: Callable[[FracOrFloat], FracOrFloat],
    matrix: AnyMatrix,
    /,
    *,
    mutable: Literal[False] = False,
) -> Matrix_M: ...


@overload
def matrix_unary(
    op: Callable[[FracOrFloat], FracOrFloat],
    matrix: AnyMatrix,
    /,
    *,
    mutable: Literal[True],
) -> MutableMatrix: ...


def matrix_unary(
    op: Callable[[FracOrFloat], FracOrFloat], matrix: AnyMatrix, /, *, mutable=False
) -> AnyMatrix:
    fn = list if mutable else tuple
    return fn(fn(op(item) for item in row) for row in matrix)


def matrix_unary_inplace(
    matrix: MutableMatrix, op: Callable[[FracOrFloat], FracOrFloat]
) -> None:
    for row in matrix:
        for j, item in enumerate(row):
            row[j] = op(item)


matrix_neg = partial(matrix_unary, operator.neg)


def matrix_binary(
    op: Callable[[FracOrFloat, FracOrFloat], FracOrFloat],
    matrix1: AnyMatrix,
    matrix2: AnyMatrix,
    /,
    *,
    mutable: bool = False,
):
    fn = list if mutable else tuple
    return fn(
        fn(op(item1, item2) for item1, item2 in zip(row1, row2, strict=True))
        for row1, row2 in zip(matrix1, matrix2, strict=True)
    )


matrix_sub = partial(matrix_binary, operator.sub)


def matrix_scalar_multiply(matrix: AnyMatrix, scalar: FracOrFloat, /, *, mutable=False):
    return matrix_unary(lambda x: x * scalar, matrix, mutable=mutable)


def matrix_linear_map_3x3(matrix: Matrix_3x3, values: Tuple3) -> Tuple3:
    value1, value2, value3 = values
    return (
        (matrix[0][0] * value1 + matrix[0][1] * value2 + matrix[0][2] * value3),
        (matrix[1][0] * value1 + matrix[1][1] * value2 + matrix[1][2] * value3),
        (matrix[2][0] * value1 + matrix[2][1] * value2 + matrix[2][2] * value3),
    )


def matrix_linear_map_3x3_fma(matrix: Matrix_3x3, values: Tuple3) -> Tuple3:
    value1, value2, value3 = values
    return (
        fma(matrix[0][0], value1, fma(matrix[0][1], value2, matrix[0][2] * value3)),
        fma(matrix[1][0], value1, fma(matrix[1][1], value2, matrix[1][2] * value3)),
        fma(matrix[2][0], value1, fma(matrix[2][1], value2, matrix[2][2] * value3)),
    )


def first_of[V](
    s: Sequence[V], fn: Callable[[V], bool], *, start: int = 0
) -> tuple[int, V]:
    for i, item in enumerate(s[start:], start):
        if fn(item):
            return i, item
    raise LookupError


def max_of[V, W: FracOrFloat](s: Sequence[V], fn: Callable[[V], W]) -> tuple[int, V, W]:
    i_max = 0
    item_max = s[0]
    maximum = fn(item_max)
    for i, item in enumerate(s):
        o = fn(item)
        if o > maximum:
            i_max = i
            item_max = item
            maximum = o
    return i_max, item_max, maximum


@overload
def matrix_reduced_row_echelon_det(
    matrix: Matrix_M, *, inplace: Literal[False] = False
) -> tuple[MutableMatrix, FracOrFloat]: ...


@overload
def matrix_reduced_row_echelon_det(
    matrix: MutableMatrix, *, inplace: bool = False
) -> tuple[MutableMatrix, FracOrFloat]: ...


def matrix_reduced_row_echelon_det(
    matrix, *, inplace=False
) -> tuple[MutableMatrix, FracOrFloat]:
    """The first value of the returned tuple is the reduced row echelon.
    The second value represents the determinant if the matrix is a square matrix."""
    if not isinstance(matrix, MutableSequence) or not inplace:
        matrix = matrix_copy(cast(AnyMatrix, matrix), mutable=True)
    matrix = cast(MutableMatrix, matrix)
    return _matrix_reduced_row_echelon(matrix)


def _matrix_reduced_row_echelon(matrix):
    # https://en.wikipedia.org/wiki/Gaussian_elimination
    m, n = matrix_size(matrix)
    determinant = 1
    h = 0  #   Initialization of the pivot row
    k = 0  #   Initialization of the pivot column
    # Row echelon form
    while h < m and k < n:
        # Find the pivot
        a_max, _, max_ab = max_of(matrix_column_values(matrix, k)[h:], abs)
        if max_ab == 0:
            # No pivot in this column
            k += 1
            continue
        # Swap the rows
        if a_max != 0:
            determinant = -determinant
            matrix[h], matrix[a_max + h] = matrix[a_max + h], matrix[h]

        row_h = matrix[h]
        determinant *= row_h[k]
        # Do for all rows below pivot
        for i in range(h + 1, m):
            row_i = matrix[i]
            f = frac(row_i[k], row_h[k])
            row_i[k] = 0
            # Do for all remaining elements in current row
            for j in range(k + 1, n):
                row_i[j] -= row_h[j] * f
        h += 1
        k += 1
    # Reduce to leading 1
    for h_, row in enumerate(reversed(matrix)):
        h = m - h_ - 1
        try:
            col_pivot, pivot = first_of(row, lambda x: x != 0, start=h)
        except LookupError:
            # This is a row of all zeroes
            determinant = 0
            continue
        # Normalize this row to leading 1
        row = matrix[h] = [frac(x, pivot) for x in row]
        # and subtract from the rows above it a scalar-multiplied version of this row
        for row_above in matrix[:h]:
            coeff = row_above[col_pivot]
            row_above[col_pivot:] = [
                b - coeff * a for a, b in zip(row[col_pivot:], row_above[col_pivot:])
            ]
    return matrix, determinant


def matrix_augment(matrix: AnyMatrix, matrix2: AnyMatrix) -> MutableMatrix:
    m = matrix_copy(matrix, mutable=True)
    for row, row2 in zip(m, matrix2, strict=True):
        row.extend(row2)
    return m


def matrix_split(
    matrix: AnyMatrix, n: int, *, mutable=False
) -> tuple[AnyMatrix, AnyMatrix]:
    fn = list if mutable else tuple
    output1 = []
    output2 = []
    for row in matrix:
        output1.append(fn(row[0:n]))
        output2.append(fn(row[n:]))
    return fn(output1), fn(output2)


def matrix_inverse_det(
    matrix: AnyMatrix, *, mutable=False
) -> tuple[AnyMatrix, FracOrFloat]:
    m, n = matrix_size(matrix)
    if m != n:
        raise ValueError(f"Expected square matrix, got {m} x {n} matrix")
    if m == 2:
        (a, b), (c, d) = cast(Matrix_2x2, matrix)
        det = a * d - b * c
        A = frac(d, det)
        B = frac(-b, det)
        C = frac(-c, det)
        D = frac(a, det)
        if mutable:
            return [[A, B], [C, D]], det
        return ((A, B), (C, D)), det
    elif m == 3:
        (a, b, c), (d, e, f), (g, h, i) = cast(Matrix_3x3, matrix)
        det = a * e * i + b * f * g + c * d * h - c * e * g - b * d * i - a * f * h
        A = frac(e * i - f * h, det)
        D = frac(c * h - b * i, det)
        G = frac(b * f - c * e, det)
        B = frac(f * g - d * i, det)
        E = frac(a * i - c * g, det)
        H = frac(c * d - a * f, det)
        C = frac(d * h - e * g, det)
        F = frac(b * g - a * h, det)
        I = frac(a * e - b * d, det)
        if mutable:
            return [[A, D, G], [B, E, H], [C, F, I]], det
        return ((A, D, G), (B, E, H), (C, F, I)), det
    else:
        matrix = matrix_augment(matrix, matrix_identity(m))
        mrre, det = _matrix_reduced_row_echelon(matrix)
        identity, inverse = matrix_split(mrre, n, mutable=mutable)
        for i, row in enumerate(identity):
            if any(item != (1 if i == j else 0) for j, item in enumerate(row)):
                # The left hand matrix should be the identity matrix
                raise ArithmeticError("Matrix is not invertible")
        return inverse, det


@overload
def matrix_inverse(matrix: AnyMatrix, *, mutable: Literal[True]) -> MutableMatrix: ...


@overload
def matrix_inverse(
    matrix: Matrix_2x2, *, mutable: Literal[False] = False
) -> Matrix_2x2: ...


@overload
def matrix_inverse(
    matrix: Matrix_3x3, *, mutable: Literal[False] = False
) -> Matrix_3x3: ...


@overload
def matrix_inverse(
    matrix: AnyMatrix, *, mutable: Literal[False] = False
) -> Matrix_M: ...


def matrix_inverse(matrix: AnyMatrix, *, mutable: bool = False) -> AnyMatrix:
    return matrix_inverse_det(matrix, mutable=mutable)[0]


def matrix_determinant(matrix: AnyMatrix) -> FracOrFloat:
    m, n = matrix_size(matrix)
    if m != n:
        raise ValueError(f"Expected square matrix, got {m} x {n} matrix")
    elif m == 2:
        (a, b), (c, d) = cast(Matrix_2x2, matrix)
        return a * d - b * c
    elif m == 3:
        (a, b, c), (d, e, f), (g, h, i) = cast(Matrix_3x3, matrix)
        return a * e * i + b * f * g + c * d * h - c * e * g - b * d * i - a * f * h
    else:
        return matrix_reduced_row_echelon_det(matrix)[1]


@overload
def matrix_multiply(
    matrix1: AnyMatrix, matrix2: AnyMatrix, *, mutable: Literal[False] = False
) -> Matrix_M: ...


@overload
def matrix_multiply(
    matrix1: AnyMatrix, matrix2: AnyMatrix, *, mutable: Literal[True]
) -> MutableMatrix: ...


def matrix_multiply(
    matrix1: AnyMatrix, matrix2: AnyMatrix, *, mutable=False
) -> Matrix_M | MutableMatrix:
    fn = list if mutable else tuple
    m, n1 = matrix_size(matrix1)
    m2, p = matrix_size(matrix2)
    if n1 != m2:
        raise ValueError(f"Cannot multiply {m} x {n1} matrix with {m2} x {p} matrix")
    return fn(
        fn(sum(matrix1[i][k] * matrix2[k][j] for k in range(n1)) for j in range(p))
        for i in range(m)
    )


def matrix_dot_product(matrix1: Matrix_Mx1, matrix2: Matrix_Mx1) -> FracOrFloat:
    return sum(a * b for (a,), (b,) in zip(matrix1, matrix2, strict=True))


def matrix_cross_product(matrix1: Matrix_3x1, matrix2: Matrix_3x1) -> Matrix_3x1:
    ((x1,), (y1,), (z1,)) = matrix1
    ((x2,), (y2,), (z2,)) = matrix2
    return ((y1 * z2 - z1 * y2,), (z1 * x2 - x1 * z2,), (x1 * y2 - y1 * x2,))


def vector_op(op, *vectors: Iterable[FracOrFloat]):
    return tuple(op(*v) for v in zip(*vectors, strict=True))


def vector_add(*vectors: Iterable[FracOrFloat]):
    return tuple(sum(v) for v in zip(*vectors, strict=True))

def vector_scalar_mul(vector: Iterable[FracOrFloat], multiplicand: FracOrFloat):
    return tuple(v * multiplicand for v in vector)

vector_neg = partial(vector_op, operator.neg)
vector_sub = partial(vector_op, operator.sub)


def vector_length_sq(vector: Iterable[FracOrFloat]) -> FracOrFloat:
    return sum(vector_op(lambda x: x * x, vector))


def vector_length(vector: Iterable[FracOrFloat]) -> float:
    return sqrt(vector_length_sq(vector))


def vector_cosine(
    vector1: Iterable[FracOrFloat], vector2: Iterable[FracOrFloat]
) -> float:
    vector1 = tuple(vector1)
    vector2 = tuple(vector2)
    dot = vector_dot_product(vector1, vector2)
    x = sqrt(dot * dot / (vector_length_sq(vector1) * vector_length_sq(vector2)))
    if dot < 0:
        return -x
    return x


def vector_dot_product(
    vector1: Iterable[FracOrFloat], vector2: Iterable[FracOrFloat]
) -> FracOrFloat:
    return sum(a * b for a, b in zip(vector1, vector2, strict=True))


def vector_cross_product(vector1: Tuple3, vector2: Tuple3) -> Tuple3:
    x1, y1, z1 = vector1
    x2, y2, z2 = vector2
    return (y1 * z2 - z1 * y2, z1 * x2 - x1 * z2, x1 * y2 - y1 * x2)
