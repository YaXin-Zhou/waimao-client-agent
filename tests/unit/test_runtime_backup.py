from scripts.backup_runtime import backup


def test_backup_copies_database_without_overwriting(tmp_path):
    database = tmp_path / "acquisition.db"
    destination = tmp_path / "backups"
    database.write_bytes(b"sqlite-test")

    target = backup(database, destination)

    assert target.is_file()
    assert target.read_bytes() == b"sqlite-test"
