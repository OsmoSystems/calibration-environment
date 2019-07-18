import logging
import traceback

import backoff


def _retry_handler(details):
    logging.info(
        f"Retrying after error. Call details: {details}. Traceback: {traceback.format_exc()}"
    )


def retry_on_exception(expected_exception, **backoff_kwargs):
    """ When used as a decorator, when the wrapped function raises expected_exception, we'll retry
    We will retry up to 10 times with an interval and jitter designed to allow temporary issues with our instruments to
    go away. We'll also log the traceback and call details of any errors that happen.

    After 10 retries, the 11th error will be raised.

    Example usage:
    >>> @retry_on_exception(ExpectedError)
    >>> def thing_that_might_raise_expected_error(foo): ...

    Args:
        expected_exception: exception or tuple of exceptions to handle via retry
        **backoff_kwargs: Additional keyword arguments will be passed to `backoff.on_exception`.

    Returns:
        decorator which can be used to wrap a function
    """
    return backoff.on_exception(
        backoff.constant,  # Use a constant interval between retries rather than, say, an exponential backoff
        expected_exception,
        **{
            "jitter": backoff.full_jitter,  # Prevents repeated collisions with other regularly-scheduled polling
            "interval": 0.5,
            "max_tries": 10,
            "on_backoff": _retry_handler,
            **backoff_kwargs,
        },
    )
