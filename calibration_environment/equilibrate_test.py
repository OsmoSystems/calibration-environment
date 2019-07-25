import datetime

import pandas as pd

from .equilibrate import _YSI_TEMPERATURE_FIELD_NAME, _TIMESTAMP_FIELD_NAME
from . import equilibrate as module


class TestIsTemperatureEquilibrated:
    def test_success(self):
        now = datetime.datetime.now()
        five_minutes_ago = now - datetime.timedelta(minutes=5)
        test_data = [
            {
                _YSI_TEMPERATURE_FIELD_NAME: 10.3,
                _TIMESTAMP_FIELD_NAME: five_minutes_ago,
            },
            {_YSI_TEMPERATURE_FIELD_NAME: 10.2, _TIMESTAMP_FIELD_NAME: now},
        ]
        test_data = pd.DataFrame(test_data)
        result = module._is_temperature_equilibrated(test_data)
        assert result

    def test_not_enough_data(self):
        now = datetime.datetime.now()
        four_minutes_ago = now - datetime.timedelta(minutes=4)
        test_data = [
            {
                _YSI_TEMPERATURE_FIELD_NAME: 10.3,
                _TIMESTAMP_FIELD_NAME: four_minutes_ago,
            },
            {_YSI_TEMPERATURE_FIELD_NAME: 10.2, _TIMESTAMP_FIELD_NAME: now},
        ]
        test_data = pd.DataFrame(test_data)
        result = module._is_temperature_equilibrated(test_data)
        assert not result

    def test_ignores_old_data(self):
        now = datetime.datetime.now()
        four_minutes_ago = now - datetime.timedelta(minutes=4)
        over_five_minutes_ago = now - datetime.timedelta(minutes=10)
        test_data = [
            {
                _YSI_TEMPERATURE_FIELD_NAME: 4.3,
                _TIMESTAMP_FIELD_NAME: over_five_minutes_ago,
            },
            {
                _YSI_TEMPERATURE_FIELD_NAME: 10.3,
                _TIMESTAMP_FIELD_NAME: four_minutes_ago,
            },
            {_YSI_TEMPERATURE_FIELD_NAME: 10.2, _TIMESTAMP_FIELD_NAME: now},
        ]
        test_data = pd.DataFrame(test_data)
        result = module._is_temperature_equilibrated(test_data)
        assert result


class TestWaitForTemperatureEquilibration:
    pass  # TODO
