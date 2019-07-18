from unittest.mock import sentinel

import pytest

import calibration_environment.retry as module


class CustomException(Exception):
    pass


class TestRetryOnException:
    def test_passes_through_return_value_if_it_works_the_first_time(self):
        def reliable_function(to_return):
            return to_return

        wrapped_fn = module.retry_on_exception(CustomException)(reliable_function)
        assert wrapped_fn(sentinel.happiness) == sentinel.happiness

    def test_can_retry_10_times_then_pass(self):
        tries = 0

        def unreliable_function(pass_through):
            """ Raise an exception the first 10 times this is called and then pass """
            nonlocal tries
            tries += 1
            if tries < 10:
                raise CustomException
            else:
                return pass_through

        # Meta-test: does the unreliable function actually raise?
        with pytest.raises(CustomException):
            unreliable_function(sentinel.happiness)

        tries = 0  # we used one up just now; reset it

        decorator = module.retry_on_exception(CustomException, interval=0.1)
        wrapped_fn = decorator(unreliable_function)
        assert wrapped_fn(sentinel.happiness) == sentinel.happiness

    def test_passes_through_exception_on_repeated_failure(self):
        def always_broken():
            raise CustomException

        decorator = module.retry_on_exception(CustomException, interval=0.1)
        wrapped_fn = decorator(always_broken)

        with pytest.raises(CustomException):
            wrapped_fn()
