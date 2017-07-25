from typing import List, Callable
from ww import f

__all__ = ['consume']


def consume(query_fn: Callable[[int, int], List], limit=1000, start=0, max=100,
            raise_exception=False):
    """Yield all rows from a paginated query.

    >>> import infusionsoft
    >>> query_fn = lambda page, limit: (
    ...     infusionsoft.DataService.query('mytable', limit, page, ['Id']))
    >>> all_rows = list(consume(query_fn))

    :param query_fn: Method which queries Infusionsoft and returns its rows. It
                     is passed two arguments: page number and limit.
    :param limit: Max number of rows to return on one page
    :param start: Page number to begin at
    :param max: Maximum number of pages to consume
    :param raise_exception: Whether to raise a RuntimeError if maximum number
                            of pages is exceeded. If False, number of rows is
                            silently capped.
    """
    for page in range(start, start + max + 1):
        rows = query_fn(page, limit)
        yield from rows
        if len(rows) < limit:
            break
    else:
        if raise_exception:
            raise RuntimeError(f('Maximum of {max} pages exceeded'))
