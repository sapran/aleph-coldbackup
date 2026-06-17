from aleph_coldbackup.cli import main


def test_help_exits_zero(capsys):
    try:
        rc = main(["--help"])
    except SystemExit as exc:  # argparse --help raises SystemExit(0)
        rc = exc.code
    out = capsys.readouterr().out
    assert "export" in out
    assert rc == 0
