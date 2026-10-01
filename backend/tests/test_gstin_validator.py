from backend.app.tools.gstin_validator import validate_gstin, compute_gstin_checksum

def test_valid_gstin():
    res1 = validate_gstin("27AAPFU0939F1ZV")
    assert res1.is_valid is True
    assert res1.state_code == "27"
    assert res1.pan == "AAPFU0939F"
    assert res1.entity_code == "1"
    assert res1.checksum_valid is True
    assert len(res1.errors) == 0

    res2 = validate_gstin("29AABCU9603R1ZJ")
    assert res2.is_valid is True

    res3 = validate_gstin("07AAAAA0000A1Z4")
    assert res3.is_valid is True

def test_invalid_length_gstin():
    res = validate_gstin("27AAPFU0939F1Z")  # 14 chars
    assert res.is_valid is False
    assert any("length" in e.lower() for e in res.errors)

    res_long = validate_gstin("27AAPFU0939F1ZVVV")  # 17 chars
    assert res_long.is_valid is False

def test_invalid_characters_gstin():
    # special characters inside
    res = validate_gstin("27AAPFU093@F1ZV")
    assert res.is_valid is False
    assert any("conform" in e.lower() for e in res.errors)

def test_invalid_state_code():
    res = validate_gstin("00AAPFU0939F1ZV")
    assert res.is_valid is False
    assert any("state code" in e.lower() for e in res.errors)

def test_invalid_checksum():
    # Replace valid check digit 'V' with '9'
    res = validate_gstin("27AAPFU0939F1Z9")
    assert res.is_valid is False
    assert res.checksum_valid is False
    assert any("checksum" in e.lower() for e in res.errors)

def test_empty_gstin():
    res = validate_gstin("")
    assert res.is_valid is False
    res_none = validate_gstin(None)
    assert res_none.is_valid is False
