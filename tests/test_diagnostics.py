from scripts.diagnose import evaluate_identity, present, run


def test_root_rejected():
    assert evaluate_identity({"Arn": "arn:aws:iam::123456789012:root"}, "123456789012")[0] == "FAIL"


def test_account_mismatch_and_missing_expectation_rejected():
    identity = {"Arn": "arn:aws:sts::123456789012:assumed-role/dev/session", "Account": "123456789012"}
    assert evaluate_identity(identity, "000000000000")[0] == "FAIL"
    assert evaluate_identity(identity, None)[0] == "FAIL"
    assert evaluate_identity(identity, "123456789012")[0] == "PASS"


def test_placeholder_not_a_credential(monkeypatch):
    monkeypatch.setenv("OPENAQ_API_KEY", "<API_KEY>")
    assert not present("OPENAQ_API_KEY")


def test_subprocess_errors_do_not_echo_secrets():
    import sys
    ok, message = run([sys.executable, "-c", "import sys;sys.stderr.write('secret-value');sys.exit(1)"])
    assert not ok
    assert "secret-value" not in message
