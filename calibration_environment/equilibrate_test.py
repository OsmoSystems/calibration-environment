from . import equilibrate as module


class TestWaitForTemperatureEquilibration:
    # TODO more tests

    def test_returns_on_equilibration(self, mocker):
        logging_start_time = 0
        # fmt: off
        log_values = (
            (10, 20.1),
            (20, 20.2),
            (30, 20.1),
        )
        # fmt: on

        temperature_return_sequence = [i[1] for i in log_values]
        time_time_return_sequence = [logging_start_time] + [i[0] for i in log_values]

        mocker.patch("calibration_environment.equilibrate.TEMPERATURE_MINIMUM_TIME", 30)
        mocker.patch.object(
            module.water_bath,
            "send_command_and_parse_response",
            side_effect=temperature_return_sequence,
        )
        mocker.patch("time.time", side_effect=time_time_return_sequence)

        module.wait_for_temperature_equilibration("COM99")
