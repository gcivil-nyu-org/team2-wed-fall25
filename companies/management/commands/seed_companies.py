from unittest import mock
import pytest
from companies.management.commands.seed_companies import Command


@pytest.fixture
def mock_get_or_create():
    with mock.patch("companies.management.commands.seed_companies.Company.objects.get_or_create") as m:
        # Each call returns (mocked company object, True)
        class MockCompany:
            name = "Dummy Company"

        m.side_effect = lambda **kwargs: (MockCompany(), True)
        yield m


@pytest.fixture
def mock_stdout():
    with mock.patch("sys.stdout") as m:
        yield m


def test_handle_creates_companies(mock_get_or_create):
    cmd = Command()
    # Mock stdout to capture prints
    with mock.patch.object(cmd, "stdout") as mock_out:
        with mock.patch.object(cmd, "style") as mock_style:
            # Mock SUCCESS and WARNING formatting
            mock_style.SUCCESS = lambda x: f"SUCCESS: {x}"
            mock_style.WARNING = lambda x: f"WARNING: {x}"

            cmd.handle()

            # Check get_or_create called 3 times
            assert mock_get_or_create.call_count == 3

            # Check stdout was called at least 3 times (for creations)
            assert mock_out.write.call_count >= 3


def test_handle_existing_companies(mock_get_or_create):
    # Simulate companies already exist
    mock_get_or_create.side_effect = lambda **kwargs: (mock.Mock(name="Company"), False)
    cmd = Command()
    with mock.patch.object(cmd, "stdout") as mock_out:
        with mock.patch.object(cmd, "style") as mock_style:
            mock_style.SUCCESS = lambda x: f"SUCCESS: {x}"
            mock_style.WARNING = lambda x: f"WARNING: {x}"

            cmd.handle()
            # get_or_create still called 3 times
            assert mock_get_or_create.call_count == 3
            # stdout writes should include WARNING
            written_texts = [args[0] for args, _ in mock_out.write.call_args_list]
            assert any("WARNING" in w for w in written_texts)
