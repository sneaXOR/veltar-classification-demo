from app.services.classification.layer2_validator import Layer2Validator


def test_marking_formats():
    validator = Layer2Validator()
    assert validator.validate_marking_format("EC_Not_Technical")
    assert validator.validate_marking_format("FR_EC_ML22.a")
    assert validator.validate_marking_format("DE_EC_7E001")
    assert validator.validate_marking_format("ES_EC_Technical_Not_Controlled")
    assert validator.validate_marking_format("US_EAR99")
    assert not validator.validate_marking_format("BAD_MARKING")
