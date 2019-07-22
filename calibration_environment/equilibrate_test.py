from . import equilibrate as module


class TestWaitForTemperatureEquilibration:
    # TODO a test to make sure it clears off log data older than min time

    def test_returns_on_equilibration(self, mocker):
        logging_start_time = 0
        # fmt: off
        log_values = (
            (10, 20.1),
            (20, 20.2),
            (30, 20.1),
        )
        # fmt: on

        time_return_sequence = [logging_start_time] + [i[0] for i in log_values]
        temperature_return_sequence = [i[1] for i in log_values]

        mocker.patch("calibration_environment.equilibrate.TEMPERATURE_MINIMUM_TIME", 30)
        mocker.patch.object(
            module.water_bath,
            "send_command_and_parse_response",
            side_effect=temperature_return_sequence,
        )
        # NOTE: we can't patch time.time() because logging calls will call time.time() and eat
        # up items in our sequence, so we patch a proxy function
        mocker.patch(
            "calibration_environment.equilibrate._get_current_time",
            side_effect=time_return_sequence,
        )
        mocker.patch("time.sleep", return_value=None)

        module.wait_for_temperature_equilibration("COM99")
