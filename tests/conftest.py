import pytest

from med_data.generate import generate_dataset


@pytest.fixture(scope="session")
def dataset():
    return generate_dataset()
