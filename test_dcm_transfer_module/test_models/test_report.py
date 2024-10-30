"""Test module for the `Report` data model."""

from dcm_common.models.data_model import get_model_serialization_test

from dcm_transfer_module.models import Report


test_report_json = get_model_serialization_test(
    Report, (
        ((), {"host": ""}),
    )
)


def test_report_json_data():
    """Test property `json` of model `Report`."""

    json = Report(host="").json

    assert "data" in json
