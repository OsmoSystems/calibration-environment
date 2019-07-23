from . import equilibrate as module


class TestWaitForTemperatureEquilibration:
    @staticmethod
    def _set_up_mocking(mocker, log_values, minimum_time):
        logging_start_time = 0
        time_return_sequence = [logging_start_time] + [i[0] for i in log_values]
        temperature_return_sequence = [i[1] for i in log_values]

        mocker.patch.object(module, "TEMPERATURE_MINIMUM_TIME", minimum_time)
        mock_read_temperature = mocker.patch.object(
            module.water_bath,
            "send_command_and_parse_response",
            side_effect=temperature_return_sequence,
        )
        mocker.patch.object(module, "time", side_effect=time_return_sequence)
        mocker.patch.object(module, "sleep", return_value=None)
        return mock_read_temperature

    def test_returns_on_equilibration(self, mocker):
        minimum_time = 30
        # fmt: off
        log_values = (
            (10, 20.1),
            (20, 20.2),
            (30, 20.1),
        )
        # fmt: on

        mock_read_temperature = self._set_up_mocking(mocker, log_values, minimum_time)

        module.wait_for_temperature_equilibration("COM99")
        assert mock_read_temperature.call_count == 3

    def test_trims_old_values(self, mocker):
        minimum_time = 20
        # fmt: off
        log_values = (
            (10, 5.1),
            (20, 12.2),
            (30, 22.05),
            (40, 22.),
            (50, 21.98),
        )
        # fmt: on

        mock_read_temperature = self._set_up_mocking(mocker, log_values, minimum_time)

        module.wait_for_temperature_equilibration("COM99")
        assert mock_read_temperature.call_count == 5
