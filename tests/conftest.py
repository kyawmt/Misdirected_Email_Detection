import pandas as pd
import pytest

from med_data.generate import generate_dataset

# The `ui` extra installs pyarrow (a Streamlit dependency). When pyarrow is
# importable, pandas 3 stores strings in Arrow by default. The pipeline gives
# the same results either way, but runs about three times slower with Arrow
# strings, so tests use the Python string storage the pipeline was built with.
pd.set_option("mode.string_storage", "python")


@pytest.fixture(scope="session")
def dataset():
    return generate_dataset()


@pytest.fixture(scope="session")
def validation_checks(dataset):
    """The quality checks on the generated session dataset, run once for the whole session.

    They are a pure function of the unmodified dataset, and two tests need exactly this result: the
    contract test and the write and read round trip (`write_dataset` runs the checks to write the
    quality report, even with `validate=False`). A test that changes a table builds a new dataset and
    runs its own full validation; none of them reuses this list.
    """
    from med_data.validate import validate_dataset

    return validate_dataset(dataset)
