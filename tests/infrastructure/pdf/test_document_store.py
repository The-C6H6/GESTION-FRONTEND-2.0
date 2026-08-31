import asyncio

import pytest

from esiqie_dictamenes.core.errors import PdfDestinationError, PdfSaveError
from esiqie_dictamenes.infrastructure.pdf.document_store import LocalPdfDocumentStore


def test_validate_destination_keeps_an_absolute_pdf_path_without_creating_it(tmp_path):
    destination = tmp_path / "base.pdf"

    result = LocalPdfDocumentStore().validate_destination(destination)

    assert result == destination
    assert not destination.exists()


def test_validate_destination_adds_a_missing_pdf_suffix_without_creating_it(tmp_path):
    destination = tmp_path / "base"

    result = LocalPdfDocumentStore().validate_destination(destination)

    assert result == tmp_path / "base.pdf"
    assert not result.exists()


def test_validate_destination_accepts_a_custom_pdf_filename_without_creating_it(tmp_path):
    destination = tmp_path / "dictamen-personalizado.pdf"

    result = LocalPdfDocumentStore().validate_destination(destination)

    assert result == destination
    assert not destination.exists()


@pytest.mark.parametrize(
    "destination",
    [
        "dictamen.txt",
        "missing-parent/dictamen.pdf",
    ],
)
def test_validate_destination_rejects_an_invalid_file_target_without_creating_it(
    tmp_path, destination
):
    selected_path = tmp_path / destination

    with pytest.raises(PdfDestinationError):
        LocalPdfDocumentStore().validate_destination(selected_path)

    assert not selected_path.exists()


def test_validate_destination_rejects_a_directory_selected_as_a_file(tmp_path):
    selected_directory = tmp_path / "selected-directory"
    selected_directory.mkdir()

    with pytest.raises(PdfDestinationError):
        LocalPdfDocumentStore().validate_destination(selected_directory)

    assert selected_directory.is_dir()


@pytest.mark.parametrize(
    ("existing_files", "expected_name"),
    [
        ((), "base.pdf"),
        (("base.pdf",), "base_2.pdf"),
        (("base.pdf", "base_2.pdf"), "base_3.pdf"),
    ],
)
def test_save_creates_the_first_exclusively_available_pdf_without_overwriting(
    tmp_path, existing_files, expected_name
):
    contents_by_name = {
        filename: f"existing {filename}".encode() for filename in existing_files
    }
    for filename, contents in contents_by_name.items():
        (tmp_path / filename).write_bytes(contents)

    result = asyncio.run(
        LocalPdfDocumentStore().save(tmp_path / "base.pdf", b"new document")
    )

    assert result == tmp_path / expected_name
    assert result.read_bytes() == b"new document"
    assert {
        filename: (tmp_path / filename).read_bytes()
        for filename in contents_by_name
    } == contents_by_name


def test_save_removes_only_its_exact_partial_file_and_hides_document_data(tmp_path):
    existing = tmp_path / "base.pdf"
    existing.write_bytes(b"existing document")
    document = b"Ana Lopez 2021320863 private PDF bytes"

    def failing_writer(file_handle, content):
        file_handle.write(b"partial")
        raise OSError("disk failure")

    store = LocalPdfDocumentStore(writer=failing_writer)

    with pytest.raises(PdfSaveError) as captured:
        asyncio.run(store.save(existing, document))

    assert existing.read_bytes() == b"existing document"
    assert not (tmp_path / "base_2.pdf").exists()
    assert "Ana Lopez" not in str(captured.value)
    assert "2021320863" not in str(captured.value)
    assert document.decode() not in str(captured.value)
