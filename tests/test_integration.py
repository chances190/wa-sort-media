from src.organizer import organize


def test_dry_run_writes_nothing(test_db, test_media_dir, test_contacts, tmp_path):
    out_dir = tmp_path / "organized"

    count = organize(
        test_db,
        test_media_dir,
        out_dir,
        contacts=test_contacts,
        dry_run=True,
    )

    assert count == 4
    assert not out_dir.exists()


def test_copy_organizes_all_files(test_db, test_media_dir, test_contacts, tmp_path):
    out_dir = tmp_path / "organized"

    count = organize(
        test_db,
        test_media_dir,
        out_dir,
        contacts=test_contacts,
        dry_run=False,
        copy=True,
    )

    assert count == 4

    assert (out_dir / "Mom" / "Images" / "IMG-20240101-WA0001.jpg").exists()
    assert (out_dir / "Family Group" / "Video" / "VID-20240101-WA0002.mp4").exists()
    assert (out_dir / "group_987654321" / "Images" / "IMG-20240101-WA0003.jpg").exists()
    assert (out_dir / "Unmatched" / "unmatched-file.mp4").exists()

    assert (test_media_dir / "WhatsApp Images" / "IMG-20240101-WA0001.jpg").exists()
    assert (test_media_dir / "WhatsApp Video" / "VID-20240101-WA0002.mp4").exists()
    assert (test_media_dir / "WhatsApp Images" / "IMG-20240101-WA0003.jpg").exists()
    assert (test_media_dir / "WhatsApp Video" / "unmatched-file.mp4").exists()


def test_move_removes_originals(test_db, test_media_dir, test_contacts, tmp_path):
    out_dir = tmp_path / "organized"

    count = organize(
        test_db,
        test_media_dir,
        out_dir,
        contacts=test_contacts,
        dry_run=False,
        copy=False,
    )

    assert count == 4

    assert (out_dir / "Mom" / "Images" / "IMG-20240101-WA0001.jpg").exists()
    assert (out_dir / "Family Group" / "Video" / "VID-20240101-WA0002.mp4").exists()
    assert (out_dir / "group_987654321" / "Images" / "IMG-20240101-WA0003.jpg").exists()
    assert (out_dir / "Unmatched" / "unmatched-file.mp4").exists()

    assert not (test_media_dir / "WhatsApp Images" / "IMG-20240101-WA0001.jpg").exists()
    assert not (test_media_dir / "WhatsApp Video" / "VID-20240101-WA0002.mp4").exists()
    assert not (test_media_dir / "WhatsApp Images" / "IMG-20240101-WA0003.jpg").exists()
    assert not (test_media_dir / "WhatsApp Video" / "unmatched-file.mp4").exists()


def test_no_contacts_falls_back_to_phone(test_db, test_media_dir, tmp_path):
    out_dir = tmp_path / "organized"

    organize(
        test_db,
        test_media_dir,
        out_dir,
        contacts=None,
        dry_run=False,
        copy=True,
    )

    assert (out_dir / "+5511999999999" / "Images" / "IMG-20240101-WA0001.jpg").exists()
    assert (out_dir / "Family Group" / "Video" / "VID-20240101-WA0002.mp4").exists()
    assert (out_dir / "group_987654321" / "Images" / "IMG-20240101-WA0003.jpg").exists()
