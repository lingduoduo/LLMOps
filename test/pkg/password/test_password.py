import base64

import pytest

from pkg.password import validate_password, hash_password, compare_password


# --------------------------
# Fixtures
# --------------------------
@pytest.fixture
def salt16():
    """Deterministic 16-byte salt (no randomness, stable tests)."""
    return b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10"


@pytest.fixture
def other_salt16():
    """Different deterministic salt to verify salt sensitivity."""
    return b"\x10\x0f\x0e\x0d\x0c\x0b\x0a\x09\x08\x07\x06\x05\x04\x03\x02\x01"


# --------------------------
# Validation tests
# --------------------------
@pytest.mark.parametrize(
    "password,expected_ok",
    [
        pytest.param("Password1", True, id="valid: mixed-case + digit"),
        pytest.param("abc12345", True, id="valid: lower + digits len=8"),
        pytest.param("A1b2C3d4", True, id="valid: mixed len=8"),
        pytest.param("mypwd2025", True, id="valid: lower+digits"),
        # boundaries
        pytest.param("Abcdefg1", True, id="boundary: length=8 valid"),
        pytest.param("Abcdefghijklmn1", True, id="boundary: length=16 valid"),
        pytest.param("short1", False, id="invalid: too short len=6"),
        pytest.param("toolongpassword123", False, id="invalid: too long len>16"),
        pytest.param("allletters", False, id="invalid: no digit"),
        pytest.param("12345678", False, id="invalid: no letter"),
        pytest.param("", False, id="invalid: empty"),
        pytest.param("密码1234", False, id="invalid: non-ascii letters (regex A-Za-z only)"),
    ],
)
def test_validate_password(password, expected_ok):
    if expected_ok:
        validate_password(password)  # should not raise
    else:
        with pytest.raises(ValueError, match="Password validation failed"):
            validate_password(password)


# --------------------------
# Hashing determinism & salt sensitivity
# --------------------------
def test_hash_password_deterministic_with_same_salt(salt16):
    pwd = "Password123"
    h1 = hash_password(pwd, salt16)
    h2 = hash_password(pwd, salt16)
    assert h1 == h2, "Same password+salt must produce identical hashes"


def test_hash_password_changes_with_different_salts(salt16, other_salt16):
    pwd = "Password123"
    h1 = hash_password(pwd, salt16)
    h2 = hash_password(pwd, other_salt16)
    assert h1 != h2, "Same password with different salts must produce different hashes"


# --------------------------
# Comparison behavior
# --------------------------
@pytest.mark.parametrize(
    "password",
    [
        pytest.param("MySecret123", id="p1"),
        pytest.param("AnotherPwd456", id="p2"),
        pytest.param("TestPass789", id="p3"),
    ],
)
def test_compare_password_match_and_mismatch(password, salt16):
    hashed = hash_password(password, salt16)
    hashed_b64 = base64.b64encode(hashed)
    salt_b64 = base64.b64encode(salt16)

    assert compare_password(password, hashed_b64, salt_b64) is True
    assert compare_password(password + "x", hashed_b64, salt_b64) is False


def test_compare_password_wrong_salt_returns_false(salt16, other_salt16):
    pwd = "MySecret123"
    hashed = hash_password(pwd, salt16)
    hashed_b64 = base64.b64encode(hashed)
    wrong_salt_b64 = base64.b64encode(other_salt16)

    assert compare_password(pwd, hashed_b64, wrong_salt_b64) is False
