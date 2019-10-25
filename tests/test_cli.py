# -*- coding: utf-8 -*-

import subprocess
import sys

import pytest

import bplsqlparse


def test_cli_main_empty():
    with pytest.raises(SystemExit):
        bplsqlparse.cli.main([])


def test_parser_empty():
    with pytest.raises(SystemExit):
        parser = bplsqlparse.cli.create_parser()
        parser.parse_args([])


def test_main_help():
    # Call with the --help option as a basic sanity check.
    with pytest.raises(SystemExit) as exinfo:
        bplsqlparse.cli.main(["--help", ])
    assert exinfo.value.code == 0


def test_valid_args(filepath):
    # test doesn't abort
    path = filepath('function.sql')
    assert bplsqlparse.cli.main([path, '-r']) is not None


def test_invalid_choise(filepath):
    path = filepath('function.sql')
    with pytest.raises(SystemExit):
        bplsqlparse.cli.main([path, '-l', 'spanish'])


def test_invalid_args(filepath, capsys):
    path = filepath('function.sql')
    bplsqlparse.cli.main([path, '-r', '--indent_width', '0'])
    _, err = capsys.readouterr()
    assert err == ("[ERROR] Invalid options: indent_width requires "
                   "a positive integer\n")


def test_invalid_infile(filepath, capsys):
    path = filepath('missing.sql')
    bplsqlparse.cli.main([path, '-r'])
    _, err = capsys.readouterr()
    assert err[:22] == "[ERROR] Failed to read"


def test_invalid_outfile(filepath, capsys):
    path = filepath('function.sql')
    outpath = filepath('/missing/function.sql')
    bplsqlparse.cli.main([path, '-r', '-o', outpath])
    _, err = capsys.readouterr()
    assert err[:22] == "[ERROR] Failed to open"


def test_stdout(filepath, load_file, capsys):
    path = filepath('begintag.sql')
    expected = load_file('begintag.sql')
    bplsqlparse.cli.main([path])
    out, _ = capsys.readouterr()
    assert out == expected


def test_script():
    # Call with the --help option as a basic sanity check.
    cmd = "{0:s} -m bplsqlparse.cli --help".format(sys.executable)
    assert subprocess.call(cmd.split()) == 0


def test_encoding_utf8_stdout(filepath, load_file, capfd):
    path = filepath('encoding_utf8.sql')
    expected = load_file('encoding_utf8.sql', 'utf-8')
    sys.stdout.encoding = 'utf-8'
    bplsqlparse.cli.main([path])
    out, _ = capfd.readouterr()
    assert out == expected


def test_encoding_utf8_output_file(filepath, load_file, tmpdir):
    in_path = filepath('encoding_utf8.sql')
    expected = load_file('encoding_utf8.sql', 'utf-8')
    out_path = tmpdir.dirname + '/encoding_utf8.out.sql'
    bplsqlparse.cli.main([in_path, '-o', out_path])
    out = load_file(out_path, 'utf-8')
    assert out == expected


def test_encoding_gbk_stdout(filepath, load_file, capfd):
    path = filepath('encoding_gbk.sql')
    expected = load_file('encoding_gbk.sql', 'gbk')
    sys.stdout.encoding = 'gbk'
    bplsqlparse.cli.main([path, '--encoding', 'gbk'])
    out, _ = capfd.readouterr()
    assert out == expected


def test_encoding_gbk_output_file(filepath, load_file, tmpdir):
    in_path = filepath('encoding_gbk.sql')
    expected = load_file('encoding_gbk.sql', 'gbk')
    out_path = tmpdir.dirname + '/encoding_gbk.out.sql'
    bplsqlparse.cli.main([in_path, '--encoding', 'gbk', '-o', out_path])
    out = load_file(out_path, 'gbk')
    assert out == expected


def test_encoding_stdin_utf8(filepath, load_file, capfd):
    path = filepath('encoding_utf8.sql')
    expected = load_file('encoding_utf8.sql', 'utf-8')
    old_stdin = sys.stdin
    sys.stdin = open(path, 'r')
    sys.stdout.encoding = 'utf-8'
    bplsqlparse.cli.main(['-'])
    sys.stdin = old_stdin
    out, _ = capfd.readouterr()
    assert out == expected


def test_encoding_stdin_gbk(filepath, load_file, capfd):
    path = filepath('encoding_gbk.sql')
    expected = load_file('encoding_gbk.sql', 'gbk')
    old_stdin = sys.stdin
    sys.stdin = open(path, 'r')
    sys.stdout.encoding = 'gbk'
    bplsqlparse.cli.main(['-', '--encoding', 'gbk'])
    sys.stdin = old_stdin
    out, _ = capfd.readouterr()
    assert out == expected


def test_encoding(filepath, capsys):
    path = filepath('test_cp1251.sql')
    expected = u'insert into foo values (1); -- Песня про надежду\n'
    bplsqlparse.cli.main([path, '--encoding=cp1251'])
    out, _ = capsys.readouterr()
    assert out == expected
