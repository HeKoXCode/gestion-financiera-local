from launcher.archive_reset import normalize_archive_label


def test_archive_label_is_safe_and_readable():
    assert normalize_archive_label("Mudanza Córdoba 2026") == "mudanza-cordoba-2026"


def test_archive_label_cannot_escape_storage():
    assert normalize_archive_label("../../Datos importantes") == "datos-importantes"


def test_empty_archive_label_uses_default():
    assert normalize_archive_label(" ¿? ") == "datos"
